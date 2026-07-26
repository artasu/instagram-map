"""
海外店舗の再処理スクリプト。
Instagram スクレイピングをスキップして Claude 抽出 → Geocoding → JSON出力のみ実行。
"""
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))

from database import (
    export_locations_json,
    get_ungeocoded_locations,
    get_unprocessed_posts,
    insert_locations,
    update_location_geocoded,
    update_processed,
)
from extractor import extract_addresses
from geocoder import geocode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    # Step 1: 未処理投稿（address_found=0）を取得
    unprocessed = get_unprocessed_posts()
    if not unprocessed:
        logger.info("未処理投稿なし。")
        return

    logger.info(f"未処理投稿: {len(unprocessed)}件 → Claude API で住所抽出開始...")

    # Step 2: Claude API で住所抽出
    extraction_results = extract_addresses(unprocessed)
    result_map = {r["id"]: r for r in extraction_results}

    for post in unprocessed:
        r = result_map.get(post["id"], {"shops": []})
        shops = r.get("shops", [])
        found_shops = [s for s in shops if s.get("address")]
        update_processed(post["id"], found=len(found_shops) > 0)
        if found_shops:
            logger.info(f"  post_id={post['id']}: {len(found_shops)}件の店舗を抽出")
            for s in found_shops:
                logger.info(f"    {s.get('shop_name')} / {s.get('address')} / prefecture={s.get('prefecture')}")
            insert_locations(post["id"], found_shops)

    # Step 3: Geocoding（未完了の全 locations を対象）
    logger.info("Geocoding 実行中...")
    geocoded = 0
    for loc in get_ungeocoded_locations():
        coords = geocode(loc["address"])
        if coords:
            update_location_geocoded(loc["id"], coords[0], coords[1])
            geocoded += 1
            logger.info(f"  loc_id={loc['id']} {loc.get('shop_name')} → {coords}")
        else:
            logger.warning(f"  loc_id={loc['id']} {loc.get('shop_name')} 住所={loc.get('address')} → Geocoding失敗")

    # Step 4: locations.json 更新
    json_count = export_locations_json()
    logger.info(f"完了: Geocoding {geocoded}件, locations.json {json_count}件")


if __name__ == "__main__":
    main()
