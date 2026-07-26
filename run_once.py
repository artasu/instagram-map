"""1回だけバッチを実行して結果を表示するスクリプト。"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
sys.path.insert(0, str(Path(__file__).parent / "batch"))

from database import (
    export_locations_json,
    get_known_urls,
    get_ungeocoded_locations,
    get_unprocessed_posts,
    init_db,
    insert_locations,
    insert_new_posts,
    update_location_geocoded,
    update_processed,
)
from extractor import extract_addresses
from geocoder import geocode
from scraper import get_saved_posts, SessionError


def main():
    print("=" * 50)
    print("Instagram 保存済み投稿 1回取得テスト")
    print("=" * 50)

    init_db()

    print("\nStep 1: Instagramにログインして保存済み投稿を収集中（キャプション含む）...")
    all_posts = get_saved_posts()
    print(f"  → {len(all_posts)}件の保存済み投稿を検出")

    known_urls = get_known_urls()
    new_posts = [p for p in all_posts if p["instagram_url"] not in known_urls]
    print(f"\nStep 2: DB照合 → 新規投稿: {len(new_posts)}件")

    if new_posts:
        insert_new_posts(new_posts)
        print("  新規投稿をDBに登録しました（キャプション込み）")

    unprocessed = get_unprocessed_posts()
    if not unprocessed:
        print("  未処理投稿なし。処理をスキップします。")
        print("\n保存済み投稿一覧（全件）:")
        for i, p in enumerate(all_posts[:20], 1):
            print(f"  {i:3}. {p['instagram_url']}")
        if len(all_posts) > 20:
            print(f"  ... 他 {len(all_posts) - 20}件")
        return

    print(f"\nStep 3: Claude API で住所抽出中（{len(unprocessed)}件）...")
    results = extract_addresses(unprocessed)
    result_map = {r["id"]: r for r in results}

    total_shops = 0
    for post in unprocessed:
        r = result_map.get(post["id"], {"shops": []})
        shops = r.get("shops", [])
        found_shops = [s for s in shops if s.get("address")]
        update_processed(post["id"], found=len(found_shops) > 0)
        if found_shops:
            insert_locations(post["id"], found_shops)
            total_shops += len(found_shops)

    print(f"  → {total_shops}件の店舗を登録")

    print(f"\nStep 4: Geocoding中...")
    pinned = 0
    ungeocoded = get_ungeocoded_locations()
    for loc in ungeocoded:
        coords = geocode(loc["address"])
        if coords:
            update_location_geocoded(loc["id"], coords[0], coords[1])
            pinned += 1

    count = export_locations_json()
    print(f"\nStep 5: locations.json 更新 ({count}件)")

    print("\n" + "=" * 50)
    print(f"完了! 新規{len(new_posts)}件処理, 店舗{total_shops}件登録, ピン追加{pinned}件")
    print("=" * 50)

    # 抽出結果のサマリーを表示
    all_shops = []
    for r in results:
        for s in r.get("shops", []):
            if s.get("address"):
                all_shops.append(s)

    print(f"\n住所が見つかったお店（{len(all_shops)}件）:")
    for s in all_shops[:20]:
        print(f"  ・{s.get('shop_name', '?')} / {s.get('prefecture', '')}{s.get('city', '')} / {s.get('address', '')}")
    if len(all_shops) > 20:
        print(f"  ... 他 {len(all_shops) - 20}件")


if __name__ == "__main__":
    try:
        main()
    except SessionError as e:
        print(f"\nエラー: {e}")
        print("python login_setup.py を実行して認証してください。")
