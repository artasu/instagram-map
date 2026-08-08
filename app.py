"""
Flask APIサーバー（serve.py の後継）。
- Google OAuth によるユーザー認証
- Instagram ログイン（instagrapi 経由、per-user セッション）
- 保存済み投稿の同期バッチをバックグラウンドで実行
- locations / visits / genres / groups API

起動: python app.py
"""

import json
import logging
import os
import secrets
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_file, session

load_dotenv(Path(__file__).parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).parent
app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# 許可メールリスト（カンマ区切り）。空の場合は全員許可。
ALLOWED_EMAILS = {e.strip() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}

GOOGLE_CLIENT_ID  = os.getenv("GOOGLE_CLIENT_ID", "")
GENRES_DIR        = ROOT / "data" / "genres"
VISIT_IMAGES_DIR  = ROOT / "data" / "visit_images"
VISIT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

MIME = {
    ".html": "text/html",
    ".js":   "application/javascript",
    ".json": "application/json",
    ".css":  "text/css",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ユーザーごとの同期状態
_sync_status: dict = {}

# DB 初期化（gunicorn では __main__ ブロックが実行されないためモジュールレベルで呼ぶ）
from batch.database import init_db as _init_db
_init_db()


# ── ヘルパー ───────────────────────────────────────────────────────────────────

def _require_auth():
    """認証済みユーザーを返す。未認証なら (None, error_response) を返す。"""
    user = session.get("user")
    if not user:
        return None, (jsonify({"error": "Unauthorized"}), 401)
    return user, None


def _serve_html(name: str):
    """frontend/ の HTML を返す。プレースホルダーに API キーを注入する。"""
    path = ROOT / "frontend" / name
    if not path.exists():
        abort(404)
    content = path.read_bytes()
    content = content.replace(
        b"YOUR_GOOGLE_MAPS_API_KEY",
        os.getenv("GOOGLE_MAPS_API_KEY", "").encode(),
    )
    content = content.replace(
        b"YOUR_GOOGLE_CLIENT_ID",
        GOOGLE_CLIENT_ID.encode(),
    )
    return content, 200, {"Content-Type": "text/html; charset=utf-8"}


def _ig_session_path(user_id: str) -> Path:
    return ROOT / "user_sessions" / user_id / "ig_session.json"


# ── HTML ルート ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return _serve_html("top.html")

@app.route("/map")
def map_page():
    return _serve_html("map.html")

@app.route("/list")
def list_page():
    return _serve_html("list.html")

@app.route("/groups")
def groups_page():
    return _serve_html("groups.html")

@app.route("/settings")
def settings_page():
    return _serve_html("settings.html")

@app.route("/join")
def join_page():
    return _serve_html("join.html")

@app.route("/frontend/<path:filename>")
def frontend_static(filename):
    path = ROOT / "frontend" / filename
    if not path.exists() or not path.is_file():
        abort(404)
    mime = MIME.get(path.suffix.lower(), "application/octet-stream")
    return path.read_bytes(), 200, {"Content-Type": mime}


# ── 認証 API ───────────────────────────────────────────────────────────────────

@app.route("/api/auth/me")
def auth_me():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(user)


@app.route("/api/auth/google", methods=["POST"])
def auth_google():
    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests

    credential = (request.json or {}).get("credential")
    if not credential:
        return jsonify({"error": "credential required"}), 400
    if not GOOGLE_CLIENT_ID:
        return jsonify({"error": "GOOGLE_CLIENT_ID が未設定です。.env を確認してください。"}), 500

    try:
        info = id_token.verify_oauth2_token(
            credential, grequests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception as e:
        return jsonify({"error": f"JWT 検証失敗: {e}"}), 401

    user = {
        "id":      info["sub"],
        "email":   info.get("email", ""),
        "name":    info.get("name", ""),
        "picture": info.get("picture", ""),
    }
    if ALLOWED_EMAILS and user["email"] not in ALLOWED_EMAILS:
        logger.warning(f"auth_google: unauthorized email {user['email']!r}")
        return jsonify({"error": "このアカウントはアクセスが許可されていません。"}), 403

    session["user"] = user

    try:
        from batch.database import ensure_user
        ensure_user(user["id"], user["email"], user["name"])
    except Exception as e:
        logger.error(f"ensure_user failed for {user['id']}: {e}", exc_info=True)

    return jsonify(user)


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


# ── Instagram 認証 API ─────────────────────────────────────────────────────────

@app.route("/api/instagram/status")
def ig_status():
    user, err = _require_auth()
    if err:
        return err
    return jsonify({"connected": _ig_session_path(user["id"]).exists()})


@app.route("/api/instagram/login", methods=["POST"])
def ig_login():
    # ── 診断ログ（原因特定用） ───────────────────────────────────────────────
    logger.info(f"[ig_login] session has user={bool(session.get('user'))}, "
                f"session_keys={list(session.keys())}")

    user, err = _require_auth()
    if err:
        logger.warning("[ig_login] 401 returned by _require_auth: Google session missing")
        return err

    data     = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    logger.info(f"[ig_login] attempting login ig_user={username!r} (google_user={user['id']})")
    if not username or not password:
        return jsonify({"error": "username と password が必要です"}), 400

    try:
        from instagrapi import Client
        from instagrapi.exceptions import (
            BadPassword, TwoFactorRequired, ChallengeRequired,
            FeedbackRequired, PleaseWaitFewMinutes, LoginRequired,
            SelectContactPointRecoveryForm, RecaptchaChallengeForm,
        )

        cl = Client()
        session_path = _ig_session_path(user["id"])
        if session_path.exists():
            try:
                cl.load_settings(str(session_path))
            except Exception:
                cl = Client()

        try:
            cl.login(username, password)
        except TwoFactorRequired:
            session["ig_pending"] = {"username": username, "password": password}
            return jsonify({"two_factor_required": True}), 202
        except BadPassword as e:
            last = getattr(cl, "last_json", {})
            logger.error(f"Instagram BadPassword (user={user['id']}): last_json={last}")
            # checkpoint / challenge が BadPassword に偽装されているケースを検出
            last_str = str(last).lower()
            if "checkpoint" in last_str or "challenge" in last_str:
                return jsonify({"error": (
                    "Instagram がセキュリティチャレンジを要求しています。\n"
                    "Instagram アプリを開いて「不審なログインがありました」の通知を承認してから再試行してください。"
                )}), 401
            return jsonify({"error": "パスワードが正しくありません。Instagram のパスワードを確認してください。"}), 401
        except ChallengeRequired as e:
            logger.error(f"Instagram ChallengeRequired (user={user['id']}): {e}")
            return jsonify({"error": (
                "Instagram がセキュリティチャレンジを要求しています。\n"
                "Instagram アプリを開いて「不審なログインがありました」の通知を承認するか、"
                "しばらく待ってから再試行してください。"
            )}), 401
        except (SelectContactPointRecoveryForm, RecaptchaChallengeForm) as e:
            logger.error(f"Instagram challenge form (user={user['id']}): {type(e).__name__}: {e}")
            return jsonify({"error": (
                "Instagram がメール/SMS による本人確認を要求しています。"
                "Instagram アプリで確認コードを受け取り、承認してから再試行してください。"
            )}), 401
        except FeedbackRequired as e:
            logger.error(f"Instagram FeedbackRequired (user={user['id']}): {e}")
            return jsonify({"error": f"Instagram アカウントに問題があります: {e}"}), 401
        except PleaseWaitFewMinutes:
            return jsonify({"error": "Instagram のレート制限に達しました。数分後に再試行してください。"}), 429
        except LoginRequired as e:
            logger.error(f"Instagram LoginRequired (user={user['id']}): {e}")
            return jsonify({"error": "Instagram ログインセッションが無効です。認証情報を確認してください。"}), 401
        except Exception as e:
            logger.error(
                f"Instagram login error (user={user['id']}): {type(e).__name__}: {e}",
                exc_info=True,
            )
            return jsonify({"error": f"ログイン失敗 [{type(e).__name__}]: {e}"}), 401

        session_path.parent.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(str(session_path))
        session.pop("ig_pending", None)
        logger.info(f"Instagram login success (user={user['id']}, ig_user={username})")
        return jsonify({"ok": True})

    except Exception as e:
        logger.error(f"Instagram login unexpected error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/instagram/login/2fa", methods=["POST"])
def ig_login_2fa():
    user, err = _require_auth()
    if err:
        return err

    pending = session.get("ig_pending")
    if not pending:
        return jsonify({"error": "2FA セッションが見つかりません。ログインをやり直してください。"}), 400

    code = ((request.json or {}).get("code") or "").strip()
    if not code:
        return jsonify({"error": "認証コードが必要です"}), 400

    try:
        from instagrapi import Client
        cl = Client()
        cl.login(pending["username"], pending["password"], verification_code=code)

        session_path = _ig_session_path(user["id"])
        session_path.parent.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(str(session_path))
        session.pop("ig_pending", None)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 401


@app.route("/api/instagram/disconnect", methods=["POST"])
def ig_disconnect():
    user, err = _require_auth()
    if err:
        return err
    session_path = _ig_session_path(user["id"])
    if session_path.exists():
        session_path.unlink()
    session.pop("ig_pending", None)
    return jsonify({"ok": True})


# ── 同期 API ───────────────────────────────────────────────────────────────────

@app.route("/api/sync", methods=["POST"])
def sync_start():
    user, err = _require_auth()
    if err:
        return err

    user_id      = user["id"]
    session_path = _ig_session_path(user_id)

    if _sync_status.get(user_id, {}).get("running"):
        return jsonify({"error": "同期中です。しばらくお待ちください。"}), 409

    if not session_path.exists():
        return jsonify({"error": "Instagramにログインしてください。"}), 400

    def _run():
        _sync_status[user_id] = {"running": True, "started_at": datetime.now().isoformat()}
        try:
            from batch.main import run_batch_for_user
            run_batch_for_user(user_id, session_path)
            _sync_status[user_id] = {
                "running":      False,
                "last_success": datetime.now().isoformat(),
                "error":        None,
            }
        except Exception as e:
            logger.error(f"sync error user={user_id}: {e}", exc_info=True)
            _sync_status[user_id] = {
                "running":      False,
                "last_success": _sync_status.get(user_id, {}).get("last_success"),
                "error":        str(e),
            }

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "message": "同期を開始しました"})


@app.route("/api/sync/status")
def sync_status_api():
    user, err = _require_auth()
    if err:
        return err
    return jsonify(_sync_status.get(user["id"], {"running": False}))


# ── ロケーション API ───────────────────────────────────────────────────────────

@app.route("/api/locations")
def get_locations():
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_locations_for_user
    return jsonify(get_locations_for_user(user["id"]))


@app.route("/api/locations/normalize", methods=["POST"])
def normalize_locations():
    """同名・同住所の重複 locations を1件に統合する（既存データ修正用）。"""
    user, err = _require_auth()
    if err:
        return err
    from batch.database import normalize_duplicate_locations
    merged = normalize_duplicate_locations(user["id"])
    logger.info(f"normalize_locations: {merged} 件統合 (user={user['id']})")
    return jsonify({"ok": True, "merged": merged})


@app.route("/api/locations/<int:loc_id>", methods=["PATCH"])
def patch_location(loc_id):
    user, err = _require_auth()
    if err:
        return err
    data = request.json or {}
    from batch.database import get_location_owner, update_location_fields
    if get_location_owner(loc_id) != user["id"]:
        return jsonify({"error": "Forbidden"}), 403
    allowed = {"genre", "website_url", "official_twitter_url", "official_instagram_url"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if fields:
        update_location_fields(loc_id, fields)
    return jsonify({"ok": True})


@app.route("/api/locations/<int:loc_id>/fetch-place-info", methods=["POST"])
def fetch_place_info(loc_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_location_by_id, update_location_place_info
    loc = get_location_by_id(loc_id)
    if not loc:
        return jsonify({"error": "Not found"}), 404

    # Google Places API が設定されていれば呼び出す
    result = _call_google_places(loc.get("shop_name", ""), loc.get("address", ""))
    result["website_url"]            = result.get("website_url") or loc.get("website_url")
    result["official_twitter_url"]   = result.get("official_twitter_url") or loc.get("official_twitter_url")
    result["official_instagram_url"] = result.get("official_instagram_url") or loc.get("official_instagram_url")
    result["place_info_fetched_at"]  = datetime.now().isoformat()
    update_location_place_info(loc_id, result)
    return jsonify(result)


def _send_invite_email(to_email: str, invite_url: str, group_name: str, expires_at: str, inviter_name: str = ""):
    """Gmail SMTP (SSL) で招待メールを送信する。
    .env の GMAIL_USER（アプリ専用アカウント）/ GMAIL_APP_PASSWORD を使用。
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    gmail_user     = os.getenv("GMAIL_USER", "")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_password:
        raise ValueError("GMAIL_USER または GMAIL_APP_PASSWORD が .env に設定されていません")

    expiry_str = datetime.fromisoformat(expires_at).strftime("%Y年%m月%d日 %H:%M")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【Instagram お店マップ】グループ「{group_name}」への招待"
    msg["From"]    = gmail_user
    msg["To"]      = to_email

    from_label = f"{inviter_name}さんから" if inviter_name else ""
    body = (
        f"{from_label}グループ「{group_name}」に招待されました。\n\n"
        f"以下のリンクをクリックして参加してください:\n{invite_url}\n\n"
        f"有効期限: {expiry_str}\n\n"
        "このメールに心当たりがない場合は無視してください。"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, to_email, msg.as_string())


def _call_google_places(shop_name: str, address: str) -> dict:
    """Google Places API で店舗情報を取得する（API キー未設定時は空データを返す）。"""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or not shop_name:
        return {
            "google_rating": None, "google_ratings_total": None,
            "business_hours": None, "payment_methods": None,
            "has_parking": None, "website_url": None,
        }
    try:
        import httpx
        query  = f"{shop_name} {address}".strip()
        search = httpx.get(
            "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
            params={"input": query, "inputtype": "textquery",
                    "fields": "place_id", "key": api_key},
            timeout=10,
        ).json()
        candidates = search.get("candidates", [])
        if not candidates:
            return {"google_rating": None, "google_ratings_total": None,
                    "business_hours": None, "payment_methods": None, "has_parking": None, "website_url": None}

        place_id = candidates[0]["place_id"]
        detail   = httpx.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id,
                    "fields": "rating,user_ratings_total,opening_hours,website",
                    "language": "ja", "key": api_key},
            timeout=10,
        ).json().get("result", {})

        hours = None
        if "opening_hours" in detail:
            periods = detail["opening_hours"].get("weekday_text", [])
            hours   = periods if periods else None

        return {
            "google_rating":        detail.get("rating"),
            "google_ratings_total": detail.get("user_ratings_total"),
            "business_hours":       hours,
            "payment_methods":      None,
            "has_parking":          None,
            "website_url":          detail.get("website"),
        }
    except Exception as e:
        logger.warning(f"Google Places API error: {e}")
        return {"google_rating": None, "google_ratings_total": None,
                "business_hours": None, "payment_methods": None, "has_parking": None, "website_url": None}


# ── 訪問記録 API ───────────────────────────────────────────────────────────────

@app.route("/api/locations/<int:loc_id>/visit", methods=["GET"])
def get_visits(loc_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_visits_for_location
    return jsonify(get_visits_for_location(loc_id, user["id"]))


@app.route("/api/locations/<int:loc_id>/visit", methods=["POST"])
def create_visit(loc_id):
    user, err = _require_auth()
    if err:
        return err
    data = request.json or {}
    from batch.database import create_visit_record
    visit_id = create_visit_record(
        loc_id     = loc_id,
        user_id    = user["id"],
        visited    = int(data.get("visited", 1)),
        rating     = int(data.get("rating", 0)),
        impression = data.get("impression", ""),
        want_again = int(data.get("want_again", 0)),
        next_comment = data.get("next_comment", ""),
    )
    return jsonify({"ok": True, "visit_id": visit_id})


@app.route("/api/visits/<int:visit_id>", methods=["GET"])
def get_visit(visit_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_visit_by_id
    visit = get_visit_by_id(visit_id, user["id"])
    if not visit:
        return jsonify({"error": "Not found"}), 404
    return jsonify(visit)


@app.route("/api/visits/<int:visit_id>", methods=["PUT"])
def update_visit(visit_id):
    user, err = _require_auth()
    if err:
        return err
    data = request.json or {}
    from batch.database import update_visit_record
    if not update_visit_record(visit_id, user["id"], data):
        return jsonify({"error": "Not found or Forbidden"}), 404
    return jsonify({"ok": True})


@app.route("/api/visits/<int:visit_id>", methods=["DELETE"])
def delete_visit(visit_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import delete_visit_record
    if not delete_visit_record(visit_id, user["id"]):
        return jsonify({"error": "Not found or Forbidden"}), 404
    return jsonify({"ok": True})


@app.route("/api/locations/<int:loc_id>/visit/images", methods=["POST"])
def upload_visit_image(loc_id):
    user, err = _require_auth()
    if err:
        return err
    if "image" not in request.files:
        return jsonify({"error": "image フィールドが必要です"}), 400
    visit_id = request.form.get("visit_id")
    if not visit_id:
        return jsonify({"error": "visit_id が必要です"}), 400

    f   = request.files["image"]
    ext = Path(f.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"

    filename  = uuid.uuid4().hex + ext
    save_path = VISIT_IMAGES_DIR / filename
    f.save(str(save_path))

    from batch.database import add_visit_image
    image_id = add_visit_image(int(visit_id), filename)
    return jsonify({"ok": True, "id": image_id, "filename": filename})


@app.route("/api/visit-images/<path:filename>")
def serve_visit_image(filename):
    path = VISIT_IMAGES_DIR / Path(filename).name
    if not path.exists():
        abort(404)
    return send_file(str(path))


@app.route("/api/visit-images/<int:image_id>", methods=["DELETE"])
def delete_visit_image(image_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import delete_visit_image_record
    filename = delete_visit_image_record(image_id, user["id"])
    if filename:
        p = VISIT_IMAGES_DIR / filename
        if p.exists():
            p.unlink(missing_ok=True)
    return jsonify({"ok": True})


# ── ジャンル API ───────────────────────────────────────────────────────────────

def _genres_path(user_id: str) -> Path:
    return GENRES_DIR / f"{user_id}.json"


@app.route("/api/genres")
def get_genres():
    user, err = _require_auth()
    if err:
        return err
    p = _genres_path(user["id"])
    if p.exists():
        return app.response_class(p.read_bytes(), mimetype="application/json")
    return jsonify([])


@app.route("/api/genres", methods=["PUT"])
def put_genres():
    user, err = _require_auth()
    if err:
        return err
    GENRES_DIR.mkdir(parents=True, exist_ok=True)
    _genres_path(user["id"]).write_text(
        json.dumps(request.json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return jsonify({"ok": True})


@app.route("/api/genres/reset", methods=["POST"])
def reset_genres():
    user, err = _require_auth()
    if err:
        return err
    p = _genres_path(user["id"])
    if p.exists():
        p.unlink()
    return jsonify({"ok": True})


# ── グループ API ───────────────────────────────────────────────────────────────

@app.route("/api/groups")
def list_groups():
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_groups_for_user
    return jsonify(get_groups_for_user(user["id"]))


@app.route("/api/groups", methods=["POST"])
def create_group():
    user, err = _require_auth()
    if err:
        return err
    name = ((request.json or {}).get("name") or "").strip()
    if not name:
        return jsonify({"error": "name が必要です"}), 400
    from batch.database import create_group_record
    gid = create_group_record(name, user["id"])
    return jsonify({"ok": True, "id": gid})


@app.route("/api/groups/<int:group_id>")
def get_group(group_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_group_detail
    g = get_group_detail(group_id, user["id"])
    if not g:
        return jsonify({"error": "Not found"}), 404
    return jsonify(g)


@app.route("/api/groups/<int:group_id>", methods=["DELETE"])
def delete_group(group_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import delete_group_record
    if not delete_group_record(group_id, user["id"]):
        return jsonify({"error": "Not found or Forbidden"}), 404
    return jsonify({"ok": True})


@app.route("/api/invite-info")
def get_invite_info_api():
    """招待トークンのグループ情報を返す（認証不要）。join.html から呼ばれる。"""
    token = request.args.get("token", "").strip()
    if not token:
        return jsonify({"error": "token が必要です"}), 400
    from batch.database import get_invite_info
    info = get_invite_info(token)
    if not info:
        return jsonify({"error": "この招待リンクは無効または期限切れです"}), 404
    return jsonify(info)


@app.route("/api/groups/<int:group_id>/invite", methods=["POST"])
def generate_invite(group_id):
    """指定のメールアドレスに招待メールを送信する。"""
    user, err = _require_auth()
    if err:
        return err

    data  = request.json or {}
    email = (data.get("email") or "").strip()
    role  = (data.get("role") or "guest").strip()
    if role not in ("admin", "guest"):
        role = "guest"
    if not email:
        return jsonify({"error": "email が必要です"}), 400

    from batch.database import create_group_invite, get_group_detail, get_user_name
    g = get_group_detail(group_id, user["id"])
    if not g:
        return jsonify({"error": "Forbidden"}), 403

    token      = secrets.token_urlsafe(24)
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()
    if not create_group_invite(group_id, user["id"], token, expires_at, role):
        return jsonify({"error": "Forbidden"}), 403

    base_url     = request.host_url.rstrip("/")
    invite_url   = f"{base_url}/join?token={token}"
    inviter_name = get_user_name(user["id"])

    try:
        _send_invite_email(email, invite_url, g["name"], expires_at, inviter_name)
    except Exception as e:
        logger.error(f"招待メール送信失敗 to={email}: {e}", exc_info=True)
        return jsonify({"error": f"メール送信に失敗しました: {e}"}), 500

    return jsonify({"ok": True})


@app.route("/api/groups/<int:group_id>/members/<target_user_id>", methods=["DELETE"])
def remove_member(group_id, target_user_id):
    """管理者がメンバーを削除する。"""
    user, err = _require_auth()
    if err:
        return err
    from batch.database import remove_group_member
    if not remove_group_member(group_id, target_user_id, user["id"]):
        return jsonify({"error": "Not found or Forbidden"}), 403
    return jsonify({"ok": True})


@app.route("/api/groups/<int:group_id>/leave", methods=["POST"])
def leave_group_api(group_id):
    """メンバーがグループから退会する。"""
    user, err = _require_auth()
    if err:
        return err
    from batch.database import leave_group
    if not leave_group(group_id, user["id"]):
        return jsonify({"error": "Not found or Forbidden"}), 403
    return jsonify({"ok": True})


@app.route("/api/groups/<int:group_id>/shared-lists", methods=["POST"])
def add_shared_list(group_id):
    user, err = _require_auth()
    if err:
        return err
    col_name = ((request.json or {}).get("collection_name") or "").strip()
    if not col_name:
        return jsonify({"error": "collection_name が必要です"}), 400
    from batch.database import add_group_shared_list
    add_group_shared_list(group_id, user["id"], col_name)
    return jsonify({"ok": True})


@app.route("/api/groups/<int:group_id>/shared-lists/<int:list_id>", methods=["DELETE"])
def remove_shared_list(group_id, list_id):
    user, err = _require_auth()
    if err:
        return err
    from batch.database import remove_group_shared_list
    if not remove_group_shared_list(list_id, user["id"]):
        return jsonify({"error": "Not found or Forbidden"}), 404
    return jsonify({"ok": True})


@app.route("/api/my-collections")
def my_collections():
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_user_collections
    return jsonify(get_user_collections(user["id"]))


@app.route("/api/groups/<int:group_id>/locations")
def get_group_locations_api(group_id):
    """グループの共有リストに登録されたロケーション一覧（メンバーのみアクセス可）。"""
    user, err = _require_auth()
    if err:
        return err
    from batch.database import get_group_detail, get_locations_for_group
    g = get_group_detail(group_id, user["id"])
    if not g:
        return jsonify({"error": "Not found or Forbidden"}), 403
    return jsonify(get_locations_for_group(group_id, user["id"]))


# ── 招待参加 API ───────────────────────────────────────────────────────────────

@app.route("/api/join", methods=["POST"])
def api_join():
    user, err = _require_auth()
    if err:
        return err
    token = ((request.json or {}).get("token") or "").strip()
    if not token:
        return jsonify({"error": "token が必要です"}), 400
    from batch.database import redeem_invite
    group = redeem_invite(token, user["id"])
    if not group:
        return jsonify({"error": "無効または期限切れの招待リンクです"}), 404
    return jsonify({"ok": True, "group": group})


# ── 起動 ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true")
    print(f"サーバー起動: http://localhost:{port}/")
    print("停止するには Ctrl+C")
    app.run(host="0.0.0.0", port=port, debug=debug)
