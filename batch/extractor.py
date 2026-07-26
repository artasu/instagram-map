import logging
import os

import anthropic

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


EXTRACT_TOOL = {
    "name": "save_address_results",
    "description": "Instagram投稿キャプションから抽出したお店情報を保存する",
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "投稿のID"},
                        "shops": {
                            "type": "array",
                            "description": "投稿に含まれるすべての店舗情報（複数可、住所なしなら空配列）",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "shop_name": {
                                        "type": ["string", "null"],
                                        "description": "店名",
                                    },
                                    "address": {
                                        "type": ["string", "null"],
                                        "description": "住所（国内なら都道府県から番地まで、海外ならその国の住所フォーマットで。国名も含める）",
                                    },
                                    "prefecture": {
                                        "type": ["string", "null"],
                                        "description": "国内の場合は都道府県名（例：東京都、大阪府、北海道）、海外の場合は国名（例：タイ、シンガポール、フランス、アメリカ）",
                                    },
                                    "city": {
                                        "type": ["string", "null"],
                                        "description": "国内の場合は市区町村名（例：渋谷区、大阪市北区）、海外の場合は都市名（例：バンコク、パリ、ニューヨーク）",
                                    },
                                    "genre": {
                                        "type": ["string", "null"],
                                        "description": (
                                            "お店のジャンル（日本語で簡潔に）。"
                                            "例：カフェ、ラーメン、寿司、焼肉、居酒屋、バー、"
                                            "イタリアン、スイーツ、ベーカリー、焼き鳥、中華、など。"
                                            "不明な場合はnull。"
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
                                "required": ["address"],
                            },
                        },
                    },
                    "required": ["id", "shops"],
                },
            }
        },
        "required": ["results"],
    },
}

BATCH_SIZE = 100


def _extract_batch(client, posts):
    posts_text = "\n\n".join(
        [
            f"--- 投稿 ID:{p['id']} ---\n"
            f"URL: {p['instagram_url']}\n"
            f"キャプション:\n{p.get('caption') or '（キャプションなし）'}"
            for p in posts
        ]
    )

    prompt = f"""以下のInstagram投稿キャプションを分析し、各投稿からお店・施設情報を抽出してください。

抽出項目:
- shop_name: 店名・施設名
- address: 住所（国内なら「都道府県＋市区町村＋番地」、海外なら「現地住所＋国名」。「📍」「所在地」「アクセス」「〒」などを参考にする）
- prefecture: 【国内】都道府県（例：東京都、大阪府、北海道）/ 【海外】国名（例：タイ、シンガポール、フランス、アメリカ、ベトナム、スペイン、UAE）
- city: 【国内】市区町村（例：渋谷区、大阪市北区）/ 【海外】都市名（例：バンコク、プーケット、パリ、ニューヨーク）
- genre: お店のジャンル（カフェ、ラーメン、ホテル、テーマパーク、バーなど。日本語で簡潔に）
- recommended_menus: キャプションに登場するメニュー・料理名・商品名（最大5件）

注意:
- 国内・海外問わずお店・施設情報があれば抽出する
- 1投稿に複数店舗が含まれる場合はすべてshops配列に入れる
- 住所・場所が不明な場合のみshopsを空配列にする
- メニューはキャプションに明示されているものだけ。なければ空配列

{posts_text}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "save_address_results"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "save_address_results":
            return block.input.get("results", [])

    return []


def extract_addresses(posts):
    """
    posts: list of {id, instagram_url, caption}
    Returns: list of {id, shops: [{shop_name, address, prefecture, city, genre, recommended_menus}]}
    """
    if not posts:
        return []

    client = _get_client()
    all_results = []

    for i in range(0, len(posts), BATCH_SIZE):
        batch = posts[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(posts) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"  Claude API: バッチ {batch_num}/{total_batches} ({len(batch)}件) 処理中...")
        results = _extract_batch(client, batch)
        shop_count = sum(len(r.get("shops", [])) for r in results)
        logger.info(f"    → 店舗抽出: {shop_count}件")
        all_results.extend(results)

    total_shops = sum(len(r.get("shops", [])) for r in all_results)
    logger.info(f"  Claude API 完了: 投稿{len(all_results)}件 / 店舗{total_shops}件抽出")
    return all_results
