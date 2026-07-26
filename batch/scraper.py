import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SESSION_PATH = Path(__file__).parent.parent / "browser_state" / "session.json"
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")


class SessionError(Exception):
    pass


def _get_client():
    from instagrapi import Client
    from instagrapi.exceptions import BadPassword, LoginRequired, TwoFactorRequired

    cl = Client()

    if SESSION_PATH.exists():
        try:
            cl.load_settings(str(SESSION_PATH))
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(str(SESSION_PATH))
            logger.info("既存セッションでログイン成功")
            return cl
        except Exception as e:
            logger.info(f"セッション再利用失敗 ({e})。新規ログインします。")
            cl = Client()

    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        raise SessionError(
            "INSTAGRAM_USERNAME と INSTAGRAM_PASSWORD が .env に未設定です。\n"
            ".env ファイルを確認してください。"
        )

    try:
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    except BadPassword:
        raise SessionError(
            "パスワードが正しくありません。.env の INSTAGRAM_PASSWORD を確認してください。"
        )
    except TwoFactorRequired:
        raise SessionError(
            "2段階認証が必要です。\n"
            "python login_setup.py を実行して認証コードを入力してください。"
        )
    except LoginRequired:
        raise SessionError(
            "ログインに失敗しました。認証情報を確認してください。"
        )
    except Exception as e:
        raise SessionError(f"ログイン失敗: {e}")

    SESSION_PATH.parent.mkdir(exist_ok=True)
    cl.dump_settings(str(SESSION_PATH))
    logger.info("新規ログイン・セッション保存完了")
    return cl


def get_saved_posts():
    """
    instagrapi でスマートフォン用モバイルAPIから保存済み投稿を取得。
    キャプションも同時に取得できるため、Playwright によるブラウザ操作は不要。

    Returns: list of {instagram_url, instagram_shortcode, caption, ig_saved_at}
    """
    from instagrapi.exceptions import LoginRequired

    cl = _get_client()

    try:
        # コレクション一覧を取得し "All posts" (全保存済み) を探す
        collections = cl.collections()
        all_col = next(
            (c for c in collections if c.id == "ALL_MEDIA_AUTO_COLLECTION"),
            collections[0] if collections else None,
        )
        if all_col is None:
            raise SessionError("保存済み投稿コレクションが見つかりませんでした。")

        total = all_col.media_count or 2000
        logger.info(f"保存済み投稿コレクション: {all_col.name} ({total}件)")
        medias = cl.collection_medias(all_col.id, amount=total)

    except LoginRequired:
        raise SessionError(
            "セッションが無効です。\n"
            "python login_setup.py を実行して再ログインしてください。"
        )
    except SessionError:
        raise
    except Exception as e:
        raise SessionError(f"保存済み投稿の取得に失敗しました: {e}")

    posts = []
    for media in medias:
        posts.append(
            {
                "instagram_url": f"https://www.instagram.com/p/{media.code}/",
                "instagram_shortcode": media.code,
                "caption": media.caption_text or "",
                "ig_saved_at": int(media.taken_at.timestamp()) if media.taken_at else None,
            }
        )

    logger.info(f"保存済み投稿: {len(posts)}件を取得（キャプション含む）")
    return posts
