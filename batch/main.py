import logging
import sys
import time
from pathlib import Path

import schedule
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from database import (
    export_locations_json,
    get_known_urls,
    get_ungeocoded_locations,
    get_unprocessed_posts,
    init_db,
    insert_locations,
    insert_new_posts,
    log_batch,
    update_location_geocoded,
    update_processed,
)
from extractor import extract_addresses
from geocoder import geocode
from scraper import get_saved_posts, SessionError

LOG_PATH = Path(__file__).parent.parent / "logs" / "batch.log"
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def run_batch():
    logger.info("=" * 50)
    logger.info("バッチ開始")

    total_saved = 0
    new_count = 0
    processed_count = 0

    try:
        # Step 1: モバイルAPIで保存済み投稿をキャプション付きで収集
        logger.info("Step 1: Instagramから保存済み投稿を収集中（キャプション含む）...")
        all_posts = get_saved_posts()
        total_saved = len(all_posts)
        logger.info(f"  収集: {total_saved}件")

        # Step 2: DB照合 — 新規投稿のみ抽出
        known_urls = get_known_urls()
        new_posts = [p for p in all_posts if p["instagram_url"] not in known_urls]
        new_count = len(new_posts)
        logger.info(f"Step 2: 新規投稿: {new_count}件")

        if new_count > 0:
            insert_new_posts(new_posts)

        # Step 3: 未処理投稿を取得（新規 + 前回エラーで残ったもの）
        unprocessed = get_unprocessed_posts()
        if not unprocessed:
            logger.info("未処理投稿なし → スキップ（APIコスト: $0）")
            log_batch(total_saved, new_count, 0, "skipped")
            return

        # Step 4: Claude API で全店舗を抽出（1投稿に複数店舗対応）
        logger.info(f"Step 4: Claude API で住所抽出中（{len(unprocessed)}件）...")
        extraction_results = extract_addresses(unprocessed)
        result_map = {r["id"]: r for r in extraction_results}

        for post in unprocessed:
            r = result_map.get(post["id"], {"shops": []})
            shops = r.get("shops", [])
            found_shops = [s for s in shops if s.get("address")]
            update_processed(post["id"], found=len(found_shops) > 0)
            if found_shops:
                insert_locations(post["id"], found_shops)

        # Step 5: Geocoding（未完了の全 locations を対象）
        logger.info("Step 5: Geocoding 実行中...")
        for loc in get_ungeocoded_locations():
            coords = geocode(loc["address"])
            if coords:
                update_location_geocoded(loc["id"], coords[0], coords[1])
                processed_count += 1

        # Step 6: locations.json 全件出力（地図・リスト表示用）
        json_count = export_locations_json()
        logger.info(f"Step 6: locations.json 更新 ({json_count}件)")

        log_batch(total_saved, new_count, processed_count, "success")
        logger.info(f"バッチ完了: 新規{new_count}件 / ピン追加{processed_count}件")

    except SessionError as e:
        logger.error(f"セッションエラー: {e}")
        logger.error("→ python login_setup.py を実行してログインしてください")
        log_batch(total_saved, new_count, processed_count, "error", str(e))
    except Exception as e:
        logger.error(f"バッチエラー: {e}", exc_info=True)
        log_batch(total_saved, new_count, processed_count, "error", str(e))


def main():
    logger.info("Instagram Map バッチスケジューラー起動")
    init_db()

    run_batch()  # 初回即実行

    schedule.every(1).hours.do(run_batch)

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("バッチ停止 (Ctrl+C)")


if __name__ == "__main__":
    main()
