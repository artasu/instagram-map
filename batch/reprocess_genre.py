"""
一回限り: 既存 locations の genre / recommended_menus を
Instagram キャプションから Claude で再抽出して更新する。
実行: python batch/reprocess_genre.py
"""
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "instagram_map.db"
BATCH_SIZE = 50  # キャプションが長いので小さめに

CLASSIFY_TOOL = {
    "name": "save_genres",
    "description": "各お店のジャンルとおすすめメニューを保存する",
    "input_schema": {
        "type": "object",
        "properties": {
            "genres": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "ロケーションID"},
                        "genre": {
                            "type": "string",
                            "description": (
                                "お店のジャンル（日本語で簡潔に）。"
                                "例：カフェ、ラーメン、寿司、焼肉、居酒屋、バー、"
                                "イタリアン、スイーツ、ベーカリー、中華、など。"
                            ),
                        },
                        "recommended_menus": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "キャプションに登場するおすすめメニュー・料理名・商品名（最大5件）。"
                                "例：['抹茶ラテ', 'チーズケーキ', 'カルボナーラ']。"
                                "見当たらない場合は空配列[]。"
                            ),
                        },
                    },
                    "required": ["id", "genre", "recommended_menus"],
                },
            }
        },
        "required": ["genres"],
    },
}


def classify_batch(client, items):
    """
    items: list of {id, shop_name, address, caption}
    Returns: list of {id, genre, recommended_menus}
    """
    lines = []
    for it in items:
        lines.append(
            f"ID:{it['id']} | 店名:{it['shop_name'] or '不明'} | 住所:{it['address'] or '不明'}\n"
            f"キャプション:\n{it['caption'] or '（なし）'}"
        )
    body = "\n\n---\n\n".join(lines)

    prompt = f"""以下のInstagram投稿一覧を分析し、各お店のジャンルとおすすめメニューを抽出してください。

- ジャンルはキャプション・店名・住所から総合的に判断する
- おすすめメニューはキャプションに明示されているものだけ（最大5件）
- メニューがなければ空配列

{body}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "save_genres"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "save_genres":
            return block.input.get("genres", [])

    return []


def run():
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 全 locations を対象（キャプション付き）
    rows = conn.execute("""
        SELECT l.id AS loc_id, l.shop_name, l.address,
               COALESCE(p.caption, '') AS caption
        FROM locations l
        JOIN saved_posts p ON l.post_id = p.id
    """).fetchall()

    total_locs = len(rows)
    logger.info(f"対象 locations: {total_locs} 件（全件キャプションから再抽出）")

    items = [
        {"id": r["loc_id"], "shop_name": r["shop_name"],
         "address": r["address"], "caption": r["caption"]}
        for r in rows
    ]

    updated_count = 0
    total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"バッチ {batch_num}/{total_batches} ({len(batch)} 件) 処理中...")

        results = classify_batch(client, batch)
        logger.info(f"  → {len(results)} 件取得")

        for r in results:
            genre = r.get("genre")
            menus = r.get("recommended_menus") or []
            if not genre:
                continue
            conn.execute(
                "UPDATE locations SET genre = ?, recommended_menus = ? WHERE id = ?",
                (genre, json.dumps(menus, ensure_ascii=False), r["id"]),
            )
            updated_count += 1

        conn.commit()

    logger.info(f"完了: {updated_count} / {total_locs} 件を更新")
    conn.close()


if __name__ == "__main__":
    run()
