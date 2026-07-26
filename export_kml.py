"""
Instagram 保存済みお店 → Google マイマップ用 KML エクスポート

生成した KML ファイルを Google マイマップにインポートすると、
スマートフォンの Google マップアプリでも見られるピンマップが作成されます。

使い方:
  python export_kml.py

Google マイマップへのインポート手順:
  1. https://www.google.com/mymaps を開く（Google アカウントでログイン）
  2. 「新しい地図を作成」
  3. レイヤ名の横にある「…」→「インポート」
  4. instagram_map.kml を選択してアップロード
  5. スマートフォンの Google マップアプリ →「保存済み」→「マップ」で確認可能
"""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DB_PATH = Path(__file__).parent / "instagram_map.db"
OUTPUT_PATH = Path(__file__).parent / "instagram_map.kml"

# 都道府県 → 地方のマッピング（マイマップのレイヤ分け用）
REGION_MAP = {
    "北海道": "01_北海道",
    "青森県": "02_東北", "岩手県": "02_東北", "宮城県": "02_東北",
    "秋田県": "02_東北", "山形県": "02_東北", "福島県": "02_東北",
    "茨城県": "03_関東", "栃木県": "03_関東", "群馬県": "03_関東",
    "埼玉県": "03_関東", "千葉県": "03_関東", "東京都": "03_関東",
    "神奈川県": "03_関東",
    "新潟県": "04_中部", "富山県": "04_中部", "石川県": "04_中部",
    "福井県": "04_中部", "山梨県": "04_中部", "長野県": "04_中部",
    "岐阜県": "04_中部", "静岡県": "04_中部", "愛知県": "04_中部",
    "三重県": "05_近畿", "滋賀県": "05_近畿", "京都府": "05_近畿",
    "大阪府": "05_近畿", "兵庫県": "05_近畿", "奈良県": "05_近畿",
    "和歌山県": "05_近畿",
    "鳥取県": "06_中国", "島根県": "06_中国", "岡山県": "06_中国",
    "広島県": "06_中国", "山口県": "06_中国",
    "徳島県": "07_四国", "香川県": "07_四国", "愛媛県": "07_四国", "高知県": "07_四国",
    "福岡県": "08_九州・沖縄", "佐賀県": "08_九州・沖縄", "長崎県": "08_九州・沖縄",
    "熊本県": "08_九州・沖縄", "大分県": "08_九州・沖縄", "宮崎県": "08_九州・沖縄",
    "鹿児島県": "08_九州・沖縄", "沖縄県": "08_九州・沖縄",
}


def xml_escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def get_locations():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT p.instagram_url, l.shop_name, l.address, l.prefecture, l.city, l.lat, l.lng
           FROM locations l
           JOIN saved_posts p ON l.post_id = p.id
           WHERE l.is_geocoded = 1
           ORDER BY l.prefecture, l.city, l.shop_name"""
    ).fetchall()
    conn.close()
    return [
        {
            "instagram_url": r[0],
            "shop_name": r[1] or "（店名不明）",
            "address": r[2] or "",
            "prefecture": r[3] or "その他",
            "city": r[4] or "",
            "lat": r[5],
            "lng": r[6],
        }
        for r in rows
    ]


def build_kml(locations):
    # 都道府県 → 地方でグループ化
    by_region = defaultdict(list)
    for loc in locations:
        region = REGION_MAP.get(loc["prefecture"], "09_その他")
        by_region[region].append(loc)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        f"  <name>Instagram 保存済みお店マップ</name>",
        f"  <description>{len(locations)}件のお店（Instagramの保存済み投稿から抽出）</description>",
    ]

    for region in sorted(by_region.keys()):
        shops = by_region[region]
        # 表示名から番号プレフィックスを除去
        display_name = region.split("_", 1)[1] if "_" in region else region
        lines.append(f"  <Folder>")
        lines.append(f"    <name>{xml_escape(display_name)} ({len(shops)}件)</name>")

        # 都道府県ごとにサブフォルダ
        by_pref = defaultdict(list)
        for s in shops:
            by_pref[s["prefecture"]].append(s)

        for pref in sorted(by_pref.keys()):
            pref_shops = by_pref[pref]
            lines.append(f"    <Folder>")
            lines.append(f"      <name>{xml_escape(pref)} ({len(pref_shops)}件)</name>")

            for shop in pref_shops:
                desc = (
                    f"📍 {shop['address']}\n"
                    f"🏙 {shop['prefecture']}{shop['city']}\n"
                    f"Instagram: {shop['instagram_url']}"
                )
                lines.append(f"      <Placemark>")
                lines.append(f"        <name>{xml_escape(shop['shop_name'])}</name>")
                lines.append(f"        <description>{xml_escape(desc)}</description>")
                lines.append(f"        <Point>")
                lines.append(f"          <coordinates>{shop['lng']},{shop['lat']},0</coordinates>")
                lines.append(f"        </Point>")
                lines.append(f"      </Placemark>")

            lines.append(f"    </Folder>")

        lines.append(f"  </Folder>")

    lines.append("</Document>")
    lines.append("</kml>")
    return "\n".join(lines)


def main():
    if not DB_PATH.exists():
        print("エラー: instagram_map.db が見つかりません。先に run_once.py を実行してください。")
        sys.exit(1)

    locations = get_locations()
    if not locations:
        print("エラー: Geocoding済みの店舗データがありません。先に run_once.py を実行してください。")
        sys.exit(1)

    print(f"エクスポート対象: {len(locations)}件")

    kml_content = build_kml(locations)
    OUTPUT_PATH.write_text(kml_content, encoding="utf-8")

    print(f"KML出力完了: {OUTPUT_PATH}")
    print()
    print("=" * 50)
    print("Google マイマップへのインポート手順")
    print("=" * 50)
    print("""
1. https://www.google.com/mymaps を開く
   （Google アカウントでログイン）

2. 「新しい地図を作成」をクリック

3. 左パネルの「無題のレイヤ」横の「…」→「インポート」

4. instagram_map.kml をアップロード

5. 地図タイトルを設定（例: Instagram お店マップ）

6. スマートフォンで確認:
   Google マップアプリ →「保存済み」タブ →「マップ」
""")


if __name__ == "__main__":
    main()
