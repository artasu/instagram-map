"""
Instagram 保存済み店舗マップ - Flask バックエンドサーバー
起動: python server.py
"""
import json
import os
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
import re
import threading
import time
import urllib.request
import urllib.error

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, session
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

# ── ジャンルマスタ（DB シード用） ────────────────────────────────────────────────
DEFAULT_GENRES = [
    {"id": "cafe",          "name": "カフェ・喫茶",                  "icon": "☕",  "color": "#5D4037", "size": 1.0, "keywords": ["カフェ","喫茶","珈琲","コーヒー","coffee","cafe","純喫茶","紅茶","ティー","tea","カフェバー","カフェレストラン","ベーカリーカフェ","シェアラウンジ","動物カフェ","ブックカフェ","テーマカフェ","古民家カフェ","甘味処"]},
    {"id": "hotel",         "name": "ホテル・リゾート・温泉宿",        "icon": "🏨",  "color": "#37474F", "size": 1.0, "keywords": ["ホテル","旅館","リゾート","温泉","グランピング","宿","ラブホ","ペンション","コテージ","貸別荘"]},
    {"id": "izakaya",       "name": "居酒屋・酒場",                  "icon": "🍺",  "color": "#4E342E", "size": 1.0, "keywords": ["居酒屋","酒場","炉端","クラフトビール","ビアバー","パブ","立ち飲み","ビアホール"]},
    {"id": "ramen",         "name": "ラーメン・麺類・そば",            "icon": "🍜",  "color": "#E65100", "size": 1.0, "keywords": ["ラーメン","らーめん","拉麺","麺","うどん","そば","蕎麦","つけ麺","担々麺","蕎麦屋"]},
    {"id": "italian",       "name": "イタリアン・フレンチ・洋食",      "icon": "🍝",  "color": "#2E7D32", "size": 1.0, "keywords": ["イタリアン","イタリア","フレンチ","フランス料理","フランス菓子","ビストロ","洋食","ピザ","ピッツェリア","ダイナー","グリル"]},
    {"id": "bakery",        "name": "ベーカリー・パン屋",              "icon": "🥐",  "color": "#FF8F00", "size": 1.0, "keywords": ["ベーカリー","パン","パン屋","ブレッド","bread"]},
    {"id": "sweets",        "name": "スイーツ・デザート",              "icon": "🍰",  "color": "#AD1457", "size": 1.0, "keywords": ["スイーツ","ケーキ","パティスリー","デザート","アイス","ジェラート","クレープ","ドーナツ","チョコ","菓子","和菓子","甘味","ショコラ"]},
    {"id": "amusement",     "name": "テーマパーク・アミューズメント",  "icon": "🎡",  "color": "#7B1FA2", "size": 1.0, "keywords": ["テーマパーク","アミューズメント","遊園地","ゲームセンター","アスレチック","レジャー施設","遊び場"]},
    {"id": "restaurant",    "name": "レストラン・食堂・定食",          "icon": "🍽️", "color": "#C62828", "size": 1.0, "keywords": ["レストラン","食堂","ダイニング","定食","家庭料理","ビュッフェ","バイキング","食べ放題","ファミレス"]},
    {"id": "bar",           "name": "バー・ワインバー",                "icon": "🍷",  "color": "#1A237E", "size": 1.0, "keywords": ["バー","bar","ワインバー","ワイン","カクテル","ナイトプール","バー・レストラン"]},
    {"id": "yakiniku",      "name": "焼肉・ステーキ・肉料理",          "icon": "🥩",  "color": "#B71C1C", "size": 1.0, "keywords": ["焼肉","やきにく","ステーキ","BBQ","バーベキュー","ハンバーグ","肉","ビーフ","焼き肉"]},
    {"id": "sushi",         "name": "寿司・海鮮",                    "icon": "🍣",  "color": "#0277BD", "size": 1.0, "keywords": ["寿司","すし","鮨","海鮮","刺身","海鮮丼","海鮮レストラン"]},
    {"id": "shopping",      "name": "ショッピング・雑貨",              "icon": "🛍️", "color": "#00838F", "size": 1.0, "keywords": ["ショッピング","ショップ","雑貨","買い物","モール","百貨店","マーケット","ショッピングモール"]},
    {"id": "museum",        "name": "ミュージアム・博物館",            "icon": "🏛️", "color": "#4527A0", "size": 1.0, "keywords": ["ミュージアム","博物館","美術館","科学館","ギャラリー","展示","展覧","資料館"]},
    {"id": "ethnic",        "name": "アジア・エスニック料理",          "icon": "🌮",  "color": "#558B2F", "size": 1.0, "keywords": ["タイ","インド","メキシコ","中東","エスニック","スペイン","アジア料理","ベトナム"]},
    {"id": "tourism",       "name": "観光スポット・公園",              "icon": "🌸",  "color": "#00695C", "size": 1.0, "keywords": ["観光","公園","道の駅","名所","スポット","庭園","広場","観光地","観光スポット"]},
    {"id": "chinese",       "name": "中華料理",                      "icon": "🥟",  "color": "#D32F2F", "size": 1.0, "keywords": ["中華","中国料理","餃子","点心","飲茶","中華料理"]},
    {"id": "korean",        "name": "韓国料理",                      "icon": "🫕",  "color": "#F57F17", "size": 1.0, "keywords": ["韓国","サムギョプサル","ビビンバ","チゲ","トッポッキ","冷麺","韓国料理"]},
    {"id": "washoku",       "name": "和食・日本料理",                 "icon": "🍱",  "color": "#0288D1", "size": 1.0, "keywords": ["和食","日本料理","懐石","割烹","天ぷら","うなぎ","鰻","天麩羅","日本食"]},
    {"id": "burger",        "name": "ハンバーガー",                   "icon": "🍔",  "color": "#FF6D00", "size": 1.0, "keywords": ["ハンバーガー","burger","バーガー","キッチンカー"]},
    {"id": "curry",         "name": "カレー",                        "icon": "🍛",  "color": "#F9A825", "size": 1.0, "keywords": ["カレー","curry","スパイス","カレーライス"]},
    {"id": "yakitori",      "name": "焼き鳥・串焼き",                 "icon": "🍢",  "color": "#6D4C41", "size": 1.0, "keywords": ["焼き鳥","焼鳥","やきとり","串","串焼き","鳥料理"]},
    {"id": "spa",           "name": "スパ・サウナ・銭湯",             "icon": "🧖",  "color": "#006064", "size": 1.0, "keywords": ["サウナ","スパ","銭湯","温浴","温泉施設","スパリゾート"]},
    {"id": "experience",    "name": "体験・アクティビティ",            "icon": "🏕️", "color": "#1B5E20", "size": 1.0, "keywords": ["体験","アクティビティ","アウトドア","キャンプ","トレッキング","釣り","ものづくり"]},
    {"id": "complex",       "name": "複合施設・道の駅",               "icon": "🏢",  "color": "#546E7A", "size": 1.0, "keywords": ["複合施設","道の駅","商業施設","アウトレット"]},
    {"id": "tonkatsu",      "name": "とんかつ・揚げ物",               "icon": "🍱",  "color": "#BF360C", "size": 1.0, "keywords": ["とんかつ","揚げ物","からあげ","天丼","フライ","カツ"]},
    {"id": "entertainment", "name": "音楽・カラオケ・エンタメ",        "icon": "🎵",  "color": "#880E4F", "size": 1.0, "keywords": ["音楽","ライブ","カラオケ","スタジオ","シアター","映画","エンタメ"]},
    {"id": "other",         "name": "その他",                        "icon": "📍",  "color": "#757575", "size": 1.0, "keywords": []},
]

# ── 環境変数 ──────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
DATABASE_URL = os.getenv("DATABASE_URL")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
_USE_PG = bool(DATABASE_URL)

# ── パス ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend"
VISIT_IMAGES_DIR = BASE_DIR / "data" / "visit_images"

# ── Flask アプリ ──────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY

# ── DB アダプタ (PostgreSQL / SQLite 共通インターフェース) ─────────────────────
if _USE_PG:
    import psycopg2
    import psycopg2.extras
    import psycopg2.errors

    class _PGRow:
        """RealDictRow をラップし、インデックスアクセス (row[0]) にも対応"""
        __slots__ = ("_d", "_v")
        def __init__(self, m):
            self._d = dict(m); self._v = list(self._d.values())
        def __getitem__(self, k):
            return self._v[k] if isinstance(k, int) else self._d[k]
        def __contains__(self, k): return k in self._d
        def get(self, k, d=None): return self._d.get(k, d)
        def keys(self): return self._d.keys()
        def items(self): return self._d.items()
        def values(self): return self._d.values()
        def __iter__(self): return iter(self._d)

    class _PGCursor:
        def __init__(self, cur):
            self._cur = cur
            self.lastrowid = None
        def fetchone(self):
            r = self._cur.fetchone(); return _PGRow(r) if r else None
        def fetchall(self):
            return [_PGRow(r) for r in self._cur.fetchall()]
        def __iter__(self):
            for r in self._cur: yield _PGRow(r)

    class _PGConn:
        def __init__(self, conn): self._c = conn
        def execute(self, sql, params=()):
            cur = self._c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            adapted = sql.replace("?", "%s")
            cur.execute(adapted, params if params else None)
            pg_cur = _PGCursor(cur)
            if ("RETURNING" in adapted.upper()
                    and adapted.strip().upper().startswith("INSERT")):
                row = cur.fetchone()
                if row:
                    pg_cur.lastrowid = row.get("id")
            return pg_cur
        def executemany(self, sql, params_list):
            cur = self._c.cursor()
            cur.executemany(sql.replace("?", "%s"), params_list)
            return _PGCursor(cur)
        def commit(self): self._c.commit()
        def close(self): self._c.close()
        def rollback(self): self._c.rollback()

    def get_db() -> _PGConn:
        return _PGConn(psycopg2.connect(DATABASE_URL))

    _IntegrityError = (psycopg2.errors.UniqueViolation,)
    _RETURNING = " RETURNING id"

else:
    import sqlite3
    DB_PATH = BASE_DIR / "instagram_map.db"

    def get_db() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    _IntegrityError = (sqlite3.IntegrityError,)
    _RETURNING = ""


# ── DB 初期化 (PostgreSQL 用) ─────────────────────────────────────────────────
def _init_pg() -> None:
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                google_id TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                name TEXT,
                picture_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_groups (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (group_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                token TEXT PRIMARY KEY,
                group_id INTEGER NOT NULL,
                created_by INTEGER NOT NULL,
                expires_at TEXT,
                used_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shared_lists (
                id SERIAL PRIMARY KEY,
                group_id INTEGER NOT NULL,
                owner_user_id INTEGER NOT NULL,
                collection_name TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(group_id, owner_user_id, collection_name)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_posts (
                id SERIAL PRIMARY KEY,
                instagram_url TEXT UNIQUE NOT NULL,
                instagram_shortcode TEXT,
                caption TEXT,
                shop_name TEXT,
                address TEXT,
                prefecture TEXT,
                city TEXT,
                lat REAL,
                lng REAL,
                address_found INTEGER DEFAULT 0,
                is_geocoded INTEGER DEFAULT 0,
                ig_saved_at BIGINT,
                processed_at TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                user_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id SERIAL PRIMARY KEY,
                post_id INTEGER NOT NULL,
                shop_name TEXT,
                address TEXT,
                prefecture TEXT,
                city TEXT,
                lat REAL,
                lng REAL,
                is_geocoded INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                user_id INTEGER,
                genre TEXT,
                recommended_menus TEXT,
                google_place_id TEXT,
                business_hours TEXT,
                google_rating REAL,
                google_ratings_total INTEGER,
                payment_methods TEXT,
                has_parking INTEGER,
                website_url TEXT,
                official_twitter_url TEXT,
                official_instagram_url TEXT,
                place_info_fetched INTEGER DEFAULT 0,
                place_info_fetched_at TEXT,
                FOREIGN KEY (post_id) REFERENCES saved_posts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS genres (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#757575',
                size REAL NOT NULL DEFAULT 1.0,
                keywords TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id SERIAL PRIMARY KEY,
                location_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                visited INTEGER DEFAULT 0,
                impression TEXT,
                rating INTEGER DEFAULT 0,
                want_again INTEGER DEFAULT 0,
                next_comment TEXT,
                visited_at TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visit_images (
                id SERIAL PRIMARY KEY,
                visit_id INTEGER,
                location_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                image_data BYTEA,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS batch_log (
                id SERIAL PRIMARY KEY,
                run_at TIMESTAMPTZ DEFAULT NOW(),
                total_saved INTEGER,
                new_posts INTEGER,
                processed INTEGER,
                status TEXT,
                message TEXT
            )
        """)
        if conn.execute("SELECT COUNT(*) FROM genres").fetchone()[0] == 0:
            for i, g in enumerate(DEFAULT_GENRES):
                conn.execute(
                    "INSERT INTO genres (id, name, icon, color, size, keywords, sort_order)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (g["id"], g["name"], g["icon"], g["color"], g["size"],
                     json.dumps(g["keywords"], ensure_ascii=False), i),
                )
        conn.commit()
    finally:
        conn.close()


# ── DB 初期化 ────────────────────────────────────────────────────────────────
def init_db() -> None:
    if _USE_PG:
        _init_pg()
        return
    conn = get_db()
    try:
        # ── 新規テーブル群 ─────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_id TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                name TEXT,
                picture_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (group_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                token TEXT PRIMARY KEY,
                group_id INTEGER NOT NULL,
                created_by INTEGER NOT NULL,
                expires_at TEXT,
                used_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shared_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                owner_user_id INTEGER NOT NULL,
                collection_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, owner_user_id, collection_name)
            )
        """)

        # ── バッチ側テーブルが未作成の場合も対応（user_id 付きで作成）──────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instagram_url TEXT UNIQUE NOT NULL,
                instagram_shortcode TEXT,
                caption TEXT,
                shop_name TEXT,
                address TEXT,
                prefecture TEXT,
                city TEXT,
                lat REAL,
                lng REAL,
                address_found INTEGER DEFAULT 0,
                is_geocoded INTEGER DEFAULT 0,
                ig_saved_at INTEGER,
                processed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                shop_name TEXT,
                address TEXT,
                prefecture TEXT,
                city TEXT,
                lat REAL,
                lng REAL,
                is_geocoded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                FOREIGN KEY (post_id) REFERENCES saved_posts(id)
            )
        """)

        # ── 既存テーブルにカラムがなければ追加 ─────────────────────────────────
        for table in ("saved_posts", "locations"):
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if cols and "user_id" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")

        loc_cols = {row[1] for row in conn.execute("PRAGMA table_info(locations)")}
        if loc_cols and "genre" not in loc_cols:
            conn.execute("ALTER TABLE locations ADD COLUMN genre TEXT")
        if loc_cols and "recommended_menus" not in loc_cols:
            conn.execute("ALTER TABLE locations ADD COLUMN recommended_menus TEXT")
        for _col, _def in [
            ("google_place_id",        "TEXT"),
            ("business_hours",         "TEXT"),
            ("google_rating",          "REAL"),
            ("google_ratings_total",   "INTEGER"),
            ("payment_methods",        "TEXT"),
            ("has_parking",            "INTEGER"),
            ("website_url",            "TEXT"),
            ("official_twitter_url",   "TEXT"),
            ("official_instagram_url", "TEXT"),
            ("place_info_fetched",     "INTEGER DEFAULT 0"),
            ("place_info_fetched_at",  "TEXT"),
        ]:
            if loc_cols and _col not in loc_cols:
                conn.execute(f"ALTER TABLE locations ADD COLUMN {_col} {_def}")

        # ── ジャンルマスタテーブル ────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS genres (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#757575',
                size REAL NOT NULL DEFAULT 1.0,
                keywords TEXT NOT NULL DEFAULT '[]',
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)
        # ── 訪問記録テーブル（複数レビュー対応・UNIQUE 制約なし） ────────────
        visits_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='visits'"
        ).fetchone()
        if visits_row is None:
            conn.execute("""
                CREATE TABLE visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    visited INTEGER DEFAULT 0,
                    impression TEXT,
                    rating INTEGER DEFAULT 0,
                    want_again INTEGER DEFAULT 0,
                    next_comment TEXT,
                    visited_at TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
        elif "UNIQUE" in visits_row[0]:
            # 旧スキーマ（UNIQUE 制約あり）→ 移行
            conn.execute("ALTER TABLE visits RENAME TO visits_old")
            conn.execute("""
                CREATE TABLE visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    user_name TEXT,
                    visited INTEGER DEFAULT 0,
                    impression TEXT,
                    rating INTEGER DEFAULT 0,
                    want_again INTEGER DEFAULT 0,
                    next_comment TEXT,
                    visited_at TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT INTO visits (id, location_id, user_id, visited, impression, rating,
                                   want_again, next_comment, visited_at, updated_at)
                SELECT id, location_id, user_id, visited, impression, rating,
                       want_again, next_comment, visited_at, updated_at
                FROM visits_old
            """)
            conn.execute("DROP TABLE visits_old")
        else:
            # 既に新スキーマ。user_name カラムがなければ追加
            v_cols = {r[1] for r in conn.execute("PRAGMA table_info(visits)")}
            if "user_name" not in v_cols:
                conn.execute("ALTER TABLE visits ADD COLUMN user_name TEXT")

        # ── 訪問写真テーブル ──────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visit_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visit_id INTEGER,
                location_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 旧 DB: visit_id カラムがなければ追加して既存レコードに紐付け
        img_cols = {r[1] for r in conn.execute("PRAGMA table_info(visit_images)")}
        if "visit_id" not in img_cols:
            conn.execute("ALTER TABLE visit_images ADD COLUMN visit_id INTEGER")
            conn.execute("""
                UPDATE visit_images SET visit_id = (
                    SELECT id FROM visits
                    WHERE visits.location_id = visit_images.location_id
                      AND visits.user_id = visit_images.user_id
                    ORDER BY updated_at DESC LIMIT 1
                ) WHERE visit_id IS NULL
            """)
        VISIT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        if conn.execute("SELECT COUNT(*) FROM genres").fetchone()[0] == 0:
            for i, g in enumerate(DEFAULT_GENRES):
                conn.execute(
                    "INSERT INTO genres (id, name, icon, color, size, keywords, sort_order) VALUES (?,?,?,?,?,?,?)",
                    (g["id"], g["name"], g["icon"], g["color"], g["size"],
                     json.dumps(g["keywords"], ensure_ascii=False), i),
                )

        conn.commit()
    finally:
        conn.close()


# ── 認証デコレータ ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── HTML 注入ヘルパー ──────────────────────────────────────────────────────────
def inject_html(filepath: Path) -> Response:
    try:
        content = filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Response(f"404 Not Found: {filepath.name}", status=404, mimetype="text/plain")
    content = content.replace("YOUR_GOOGLE_MAPS_API_KEY", GOOGLE_MAPS_API_KEY)
    content = content.replace("YOUR_GOOGLE_CLIENT_ID", GOOGLE_CLIENT_ID)
    return Response(content, mimetype="text/html; charset=utf-8")


# ── HTML ルート ───────────────────────────────────────────────────────────────
@app.route("/")
def serve_top():
    return inject_html(FRONTEND_DIR / "top.html")


@app.route("/map")
def serve_map():
    return inject_html(FRONTEND_DIR / "map.html")


@app.route("/list")
def serve_list():
    return inject_html(FRONTEND_DIR / "list.html")


@app.route("/groups")
def serve_groups():
    return inject_html(FRONTEND_DIR / "groups.html")


@app.route("/join/<token>")
def serve_join(token):
    return inject_html(FRONTEND_DIR / "join.html")


@app.route("/settings")
def serve_settings():
    return inject_html(FRONTEND_DIR / "settings.html")


# ── 静的ファイル フォールバック ────────────────────────────────────────────────
@app.route("/<path:filename>")
def serve_static(filename: str):
    target = (BASE_DIR / filename).resolve()
    # パストラバーサル防止
    try:
        target.relative_to(BASE_DIR.resolve())
    except ValueError:
        return Response("Forbidden", status=403)

    if not target.exists() or not target.is_file():
        return Response("Not Found", status=404)

    if target.suffix == ".html":
        return inject_html(target)

    return send_from_directory(BASE_DIR, filename)


# ── API: 設定 ─────────────────────────────────────────────────────────────────
@app.route("/api/config")
def api_config():
    return jsonify({
        "google_maps_api_key": GOOGLE_MAPS_API_KEY,
        "google_client_id": GOOGLE_CLIENT_ID,
    })


# ── API: Google OAuth ─────────────────────────────────────────────────────────
@app.route("/api/auth/google", methods=["POST"])
def api_auth_google():
    data = request.get_json(force=True, silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"error": "credential is required"}), 400

    try:
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        return jsonify({"error": f"Invalid credential: {exc}"}), 401

    google_id = id_info["sub"]
    email = id_info.get("email", "")
    name = id_info.get("name")
    picture = id_info.get("picture")

    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO users (google_id, email, name, picture_url)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(google_id) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                picture_url = excluded.picture_url
            """,
            (google_id, email, name, picture),
        )
        conn.commit()

        user = dict(conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone())

        # 初回ログイン・最初のユーザーなら NULL user_id のデータを自分に割り当て
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if total_users == 1:
            conn.execute(
                "UPDATE saved_posts SET user_id = ? WHERE user_id IS NULL",
                (user["id"],),
            )
            conn.execute(
                "UPDATE locations SET user_id = ? WHERE user_id IS NULL",
                (user["id"],),
            )
            conn.commit()
    finally:
        conn.close()

    session["user_id"] = user["id"]
    return jsonify({
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture_url"],
    })


@app.route("/api/auth/me")
@login_required
def api_auth_me():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "User not found"}), 404
    user = dict(row)
    return jsonify({
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture_url"],
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.clear()
    return jsonify({"ok": True})


# ── API: ロケーション ──────────────────────────────────────────────────────────
@app.route("/api/locations")
@login_required
def api_locations():
    user_id = session["user_id"]
    conn = get_db()
    try:
        if not conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            session.clear()
            return jsonify({"error": "Unauthorized"}), 401
        own_rows = conn.execute(
            """
            SELECT l.id, p.instagram_url, l.shop_name, l.address, l.prefecture, l.city,
                   l.lat, l.lng, l.genre, l.recommended_menus,
                   l.business_hours, l.google_rating, l.google_ratings_total,
                   l.payment_methods, l.has_parking,
                   l.website_url, l.official_twitter_url, l.official_instagram_url,
                   COALESCE(l.place_info_fetched, 0) AS place_info_fetched,
                   l.place_info_fetched_at,
                   COALESCE(v.visited, 0) AS visited,
                   COALESCE(v.rating, 0) AS rating,
                   '' AS impression,
                   COALESCE(v.want_again, 0) AS want_again,
                   '' AS next_comment
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            LEFT JOIN (
                SELECT location_id,
                       MAX(visited) AS visited,
                       MAX(rating) AS rating,
                       MAX(want_again) AS want_again
                FROM visits WHERE user_id = ?
                GROUP BY location_id
            ) v ON l.id = v.location_id
            WHERE p.user_id = ? AND l.is_geocoded = 1
            """,
            (user_id, user_id),
        ).fetchall()

        shared_rows = conn.execute(
            """
            SELECT DISTINCT
                l.id, p.instagram_url, l.shop_name, l.address, l.prefecture, l.city,
                l.lat, l.lng, l.genre, l.recommended_menus, ug.name AS group_name,
                l.business_hours, l.google_rating, l.google_ratings_total,
                l.payment_methods, l.has_parking,
                l.website_url, l.official_twitter_url, l.official_instagram_url,
                COALESCE(l.place_info_fetched, 0) AS place_info_fetched,
                l.place_info_fetched_at,
                COALESCE(v.visited, 0) AS visited,
                COALESCE(v.rating, 0) AS rating,
                '' AS impression,
                COALESCE(v.want_again, 0) AS want_again,
                '' AS next_comment
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            JOIN shared_lists sl ON sl.owner_user_id = p.user_id
            JOIN user_groups ug ON ug.id = sl.group_id
            JOIN group_members gm ON gm.group_id = sl.group_id AND gm.user_id = ?
            LEFT JOIN (
                SELECT location_id,
                       MAX(visited) AS visited,
                       MAX(rating) AS rating,
                       MAX(want_again) AS want_again
                FROM visits WHERE user_id = ?
                GROUP BY location_id
            ) v ON l.id = v.location_id
            WHERE p.user_id != ?
              AND l.is_geocoded = 1
              AND (sl.collection_name = '__all__' OR l.prefecture = sl.collection_name)
            """,
            (user_id, user_id, user_id),
        ).fetchall()
    finally:
        conn.close()

    def _parse_row(r, source, group_name=None):
        def _jload(val):
            try:
                return json.loads(val) if val else []
            except Exception:
                return []
        return {
            "id": r["id"],
            "instagram_url": r["instagram_url"],
            "shop_name": r["shop_name"],
            "address": r["address"],
            "prefecture": r["prefecture"],
            "city": r["city"],
            "lat": r["lat"],
            "lng": r["lng"],
            "genre": r["genre"],
            "recommended_menus":    _jload(r["recommended_menus"]),
            "source": source,
            "group_name": group_name,
            "visited": r["visited"],
            "rating": r["rating"],
            "impression": r["impression"],
            "want_again": r["want_again"],
            "next_comment": r["next_comment"],
            "business_hours":        _jload(r["business_hours"]),
            "google_rating":         r["google_rating"],
            "google_ratings_total":  r["google_ratings_total"],
            "payment_methods":       _jload(r["payment_methods"]),
            "has_parking":           r["has_parking"],
            "website_url":           r["website_url"],
            "official_twitter_url":  r["official_twitter_url"],
            "official_instagram_url":r["official_instagram_url"],
            "place_info_fetched":    r["place_info_fetched"] or 0,
            "place_info_fetched_at": r["place_info_fetched_at"],
        }

    result = [_parse_row(r, "own") for r in own_rows]
    result += [_parse_row(r, "shared", r["group_name"]) for r in shared_rows]
    return jsonify(result)


# ── API: ロケーション ジャンル更新 ─────────────────────────────────────────────
@app.route("/api/locations/<int:loc_id>", methods=["PATCH"])
@login_required
def api_update_location(loc_id: int):
    user_id = session["user_id"]
    data = request.get_json(force=True, silent=True) or {}

    conn = get_db()
    try:
        row = conn.execute(
            """SELECT l.id FROM locations l
               JOIN saved_posts p ON l.post_id = p.id
               WHERE l.id = ? AND p.user_id = ?""",
            (loc_id, user_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found or forbidden"}), 404

        allowed = {"genre", "website_url", "official_twitter_url", "official_instagram_url"}
        set_clauses, values = [], []
        for field in allowed:
            if field in data:
                set_clauses.append(f"{field} = ?")
                values.append(data[field] or None)

        if not set_clauses:
            return jsonify({"error": "No fields to update"}), 400

        values.append(loc_id)
        conn.execute(
            f"UPDATE locations SET {', '.join(set_clauses)} WHERE id = ?", values
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


# ── API: 訪問記録 ─────────────────────────────────────────────────────────────
@app.route("/api/locations/<int:loc_id>/visit", methods=["GET"])
@login_required
def api_get_visit(loc_id: int):
    """当該ロケーションの全レビューを新着順で返す"""
    user_id = session["user_id"]
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT v.id, v.user_id, v.user_name, v.visited, v.impression,
                      v.rating, v.want_again, v.next_comment, v.visited_at, v.updated_at,
                      u.name AS users_name
               FROM visits v
               LEFT JOIN users u ON u.id = v.user_id
               WHERE v.location_id = ?
               ORDER BY v.updated_at DESC""",
            (loc_id,),
        ).fetchall()

        result = []
        for row in rows:
            imgs = conn.execute(
                "SELECT id, filename FROM visit_images WHERE visit_id = ? ORDER BY created_at",
                (row["id"],),
            ).fetchall()
            display_name = row["user_name"] or row["users_name"] or "ユーザー"
            result.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "user_name": display_name,
                "is_own": row["user_id"] == user_id,
                "visited": row["visited"],
                "rating": row["rating"],
                "impression": row["impression"] or "",
                "want_again": row["want_again"],
                "next_comment": row["next_comment"] or "",
                "visited_at": row["visited_at"],
                "updated_at": row["updated_at"],
                "images": [{"id": r["id"], "filename": r["filename"]} for r in imgs],
            })
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/locations/<int:loc_id>/visit", methods=["POST"])
@login_required
def api_create_visit(loc_id: int):
    """新規レビューを作成する"""
    user_id = session["user_id"]
    data = request.get_json(force=True, silent=True) or {}
    conn = get_db()
    try:
        user_row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        user_name = user_row["name"] if user_row else "ユーザー"
        visited = int(bool(data.get("visited")))
        rating = max(0, min(5, int(data.get("rating", 0))))
        impression = data.get("impression", "")
        want_again = int(bool(data.get("want_again")))
        next_comment = data.get("next_comment", "")
        now = datetime.now(timezone.utc).isoformat()
        visited_at = now if visited else None
        cur = conn.execute(
            "INSERT INTO visits (location_id, user_id, user_name, visited, impression, rating,"
            " want_again, next_comment, visited_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" + _RETURNING,
            (loc_id, user_id, user_name, visited, impression, rating,
             want_again, next_comment, visited_at, now),
        )
        visit_id = cur.lastrowid
        conn.commit()
        return jsonify({"ok": True, "visit_id": visit_id, "user_name": user_name, "updated_at": now})
    finally:
        conn.close()


@app.route("/api/visits/<int:visit_id>", methods=["GET"])
@login_required
def api_get_visit_by_id(visit_id: int):
    """特定レビューを取得する（編集モーダル用）"""
    user_id = session["user_id"]
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["user_id"] != user_id:
            return jsonify({"error": "Forbidden"}), 403
        imgs = conn.execute(
            "SELECT id, filename FROM visit_images WHERE visit_id = ? ORDER BY created_at",
            (visit_id,),
        ).fetchall()
        return jsonify({
            "id": row["id"],
            "visited": row["visited"],
            "rating": row["rating"],
            "impression": row["impression"] or "",
            "want_again": row["want_again"],
            "next_comment": row["next_comment"] or "",
            "images": [{"id": r["id"], "filename": r["filename"]} for r in imgs],
        })
    finally:
        conn.close()


@app.route("/api/visits/<int:visit_id>", methods=["DELETE"])
@login_required
def api_delete_visit(visit_id: int):
    """レビューと紐付く画像を削除する"""
    user_id = session["user_id"]
    conn = get_db()
    try:
        row = conn.execute("SELECT user_id FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["user_id"] != user_id:
            return jsonify({"error": "Forbidden"}), 403
        imgs = conn.execute(
            "SELECT filename FROM visit_images WHERE visit_id = ?", (visit_id,)
        ).fetchall()
        if not _USE_PG:
            for img in imgs:
                try:
                    (VISIT_IMAGES_DIR / img["filename"]).unlink(missing_ok=True)
                except Exception:
                    pass
        conn.execute("DELETE FROM visit_images WHERE visit_id = ?", (visit_id,))
        conn.execute("DELETE FROM visits WHERE id = ?", (visit_id,))
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/visits/<int:visit_id>", methods=["PUT"])
@login_required
def api_update_visit_by_id(visit_id: int):
    """特定レビューを更新する"""
    user_id = session["user_id"]
    data = request.get_json(force=True, silent=True) or {}
    conn = get_db()
    try:
        row = conn.execute("SELECT user_id FROM visits WHERE id = ?", (visit_id,)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if row["user_id"] != user_id:
            return jsonify({"error": "Forbidden"}), 403
        visited = int(bool(data.get("visited")))
        rating = max(0, min(5, int(data.get("rating", 0))))
        impression = data.get("impression", "")
        want_again = int(bool(data.get("want_again")))
        next_comment = data.get("next_comment", "")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE visits SET
               visited=?, impression=?, rating=?, want_again=?, next_comment=?,
               visited_at = CASE WHEN ? = 1 THEN ? ELSE visited_at END,
               updated_at = ?
               WHERE id = ?""",
            (visited, impression, rating, want_again, next_comment,
             visited, now, now, visit_id),
        )
        conn.commit()
        return jsonify({"ok": True})
    finally:
        conn.close()


# ── API: 訪問写真 ──────────────────────────────────────────────────────────────
@app.route("/api/locations/<int:loc_id>/visit/images", methods=["POST"])
@login_required
def api_upload_visit_image(loc_id: int):
    user_id = session["user_id"]
    visit_id = request.form.get("visit_id", type=int)
    if not visit_id:
        return jsonify({"error": "visit_id required"}), 400
    conn = get_db()
    try:
        vrow = conn.execute(
            "SELECT user_id FROM visits WHERE id = ? AND location_id = ?",
            (visit_id, loc_id),
        ).fetchone()
        if not vrow or vrow["user_id"] != user_id:
            return jsonify({"error": "Forbidden"}), 403
        if "image" not in request.files:
            return jsonify({"error": "No image"}), 400
        file = request.files["image"]
        ext = Path(file.filename).suffix.lower() if file.filename else ""
        if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            return jsonify({"error": "Invalid file type"}), 400
        filename = f"{secrets.token_hex(16)}{ext}"
        if _USE_PG:
            file_data = psycopg2.Binary(file.read())
            cur = conn.execute(
                "INSERT INTO visit_images (visit_id, location_id, user_id, filename, image_data)"
                " VALUES (?,?,?,?,?) RETURNING id",
                (visit_id, loc_id, user_id, filename, file_data),
            )
        else:
            VISIT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            file.save(VISIT_IMAGES_DIR / filename)
            cur = conn.execute(
                "INSERT INTO visit_images (visit_id, location_id, user_id, filename)"
                " VALUES (?,?,?,?)",
                (visit_id, loc_id, user_id, filename),
            )
        conn.commit()
        image_id = cur.lastrowid
    finally:
        conn.close()
    return jsonify({"id": image_id, "filename": filename})


@app.route("/api/visit-images/<filename>")
@login_required
def serve_visit_image(filename: str):
    p = Path(filename)
    stem, ext = p.stem, p.suffix.lower()
    if (not stem
            or not all(c in "0123456789abcdef" for c in stem)
            or ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            or ".." in filename):
        return jsonify({"error": "Not found"}), 404
    if _USE_PG:
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT image_data FROM visit_images WHERE filename = ?", (filename,)
            ).fetchone()
        finally:
            conn.close()
        if not row or not row["image_data"]:
            return jsonify({"error": "Not found"}), 404
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".gif": "image/gif", ".webp": "image/webp"}
        return Response(bytes(row["image_data"]), mimetype=mime_map.get(ext, "image/jpeg"))
    return send_from_directory(VISIT_IMAGES_DIR, filename)


@app.route("/api/visit-images/<int:image_id>", methods=["DELETE"])
@login_required
def api_delete_visit_image(image_id: int):
    user_id = session["user_id"]
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM visit_images WHERE id = ? AND user_id = ?",
            (image_id, user_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        if not _USE_PG:
            try:
                (VISIT_IMAGES_DIR / row["filename"]).unlink(missing_ok=True)
            except Exception:
                pass
        conn.execute("DELETE FROM visit_images WHERE id = ?", (image_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ── API: ジャンルマスタ ────────────────────────────────────────────────────────
@app.route("/api/genres", methods=["GET"])
def api_get_genres():
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM genres ORDER BY sort_order").fetchall()
        return jsonify([
            {**dict(r), "keywords": json.loads(r["keywords"])}
            for r in rows
        ])
    finally:
        conn.close()


@app.route("/api/genres", methods=["PUT"])
@login_required
def api_update_genres():
    genres = request.get_json(force=True, silent=True) or []
    conn = get_db()
    try:
        conn.execute("DELETE FROM genres")
        for i, g in enumerate(genres):
            conn.execute(
                "INSERT INTO genres (id, name, icon, color, size, keywords, sort_order) VALUES (?,?,?,?,?,?,?)",
                (g["id"], g["name"], g["icon"], g.get("color", "#757575"), g.get("size", 1.0),
                 json.dumps(g.get("keywords", []), ensure_ascii=False), i),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/genres/reset", methods=["POST"])
@login_required
def api_reset_genres():
    conn = get_db()
    try:
        conn.execute("DELETE FROM genres")
        for i, g in enumerate(DEFAULT_GENRES):
            conn.execute(
                "INSERT INTO genres (id, name, icon, color, size, keywords, sort_order) VALUES (?,?,?,?,?,?,?)",
                (g["id"], g["name"], g["icon"], g["color"], g["size"],
                 json.dumps(g["keywords"], ensure_ascii=False), i),
            )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ── API: 重複ロケーション削除 ──────────────────────────────────────────────────
@app.route("/api/locations/deduplicate", methods=["POST"])
@login_required
def api_deduplicate_locations():
    """同一ユーザーで shop_name が重複するロケーションを統合する。
    レビューがある方（なければ id が大きい方）を残し、他を削除する。"""
    user_id = session["user_id"]
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT l.id, l.shop_name,
                   (SELECT COUNT(*) FROM visits WHERE location_id = l.id) AS visit_count
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            WHERE p.user_id = ?
            ORDER BY l.shop_name,
                     (SELECT COUNT(*) FROM visits WHERE location_id = l.id) DESC,
                     l.id DESC
            """,
            (user_id,),
        ).fetchall()

        from collections import defaultdict
        groups = defaultdict(list)
        for r in rows:
            name = (r["shop_name"] or "").strip()
            if name:
                groups[name].append(r["id"])

        deleted = 0
        for name, ids in groups.items():
            if len(ids) <= 1:
                continue
            winner_id = ids[0]
            loser_ids = ids[1:]
            ph = ",".join("?" * len(loser_ids))
            # visits を winner に付け替え
            conn.execute(
                f"UPDATE visits SET location_id = ? WHERE location_id IN ({ph})",
                [winner_id] + loser_ids,
            )
            # visit_images (旧スタイル: visit_id なし) を winner に付け替え
            conn.execute(
                f"UPDATE visit_images SET location_id = ? WHERE location_id IN ({ph}) AND visit_id IS NULL",
                [winner_id] + loser_ids,
            )
            conn.execute(f"DELETE FROM locations WHERE id IN ({ph})", loser_ids)
            deleted += len(loser_ids)

        conn.commit()
        return jsonify({"ok": True, "deleted": deleted})
    finally:
        conn.close()


# ── API: Places 情報取得 ───────────────────────────────────────────────────────
@app.route("/api/locations/<int:loc_id>/fetch-place-info", methods=["POST"])
@login_required
def api_fetch_place_info(loc_id: int):
    """Google Places API でお店情報を取得・DB 更新し結果を返す。"""
    if not GOOGLE_MAPS_API_KEY:
        return jsonify({"error": "API key not configured"}), 503

    result = _fetch_place_info(loc_id)

    conn = get_db()
    try:
        row = conn.execute(
            """SELECT business_hours, google_rating, google_ratings_total,
                      payment_methods, has_parking,
                      website_url, official_twitter_url, official_instagram_url,
                      place_info_fetched
               FROM locations WHERE id=?""",
            (loc_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"error": "Not found"}), 404

    def _jload(val):
        try: return json.loads(val) if val else []
        except: return []

    return jsonify({
        "ok":                    True,
        "business_hours":        _jload(row["business_hours"]),
        "google_rating":         row["google_rating"],
        "google_ratings_total":  row["google_ratings_total"],
        "payment_methods":       _jload(row["payment_methods"]),
        "has_parking":           row["has_parking"],
        "website_url":           row["website_url"],
        "official_twitter_url":  row["official_twitter_url"],
        "official_instagram_url":row["official_instagram_url"],
    })


# ── API: マイコレクション ──────────────────────────────────────────────────────
@app.route("/api/my-collections")
@login_required
def api_my_collections():
    user_id = session["user_id"]
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT l.prefecture, COUNT(*) AS cnt
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            WHERE p.user_id = ? AND l.is_geocoded = 1
            GROUP BY l.prefecture
            ORDER BY cnt DESC
            """,
            (user_id,),
        ).fetchall()
        total = conn.execute(
            """
            SELECT COUNT(*)
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            WHERE p.user_id = ? AND l.is_geocoded = 1
            """,
            (user_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    collections = [{"name": "__all__", "label": "全件", "count": total}]
    for r in rows:
        pref = r["prefecture"] or "不明"
        collections.append({"name": pref, "label": pref, "count": r["cnt"]})
    return jsonify(collections)


# ── API: グループ一覧 / 作成 ───────────────────────────────────────────────────
@app.route("/api/groups", methods=["GET"])
@login_required
def api_get_groups():
    user_id = session["user_id"]
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT ug.id, ug.name, ug.owner_id, ug.created_at,
                   (SELECT COUNT(*) FROM group_members WHERE group_id = ug.id) AS member_count,
                   (SELECT COUNT(*) FROM shared_lists WHERE group_id = ug.id) AS shared_count
            FROM user_groups ug
            JOIN group_members gm ON gm.group_id = ug.id
            WHERE gm.user_id = ?
            ORDER BY ug.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["is_owner"] = (d["owner_id"] == user_id)
        result.append(d)
    return jsonify(result)


@app.route("/api/groups", methods=["POST"])
@login_required
def api_create_group():
    user_id = session["user_id"]
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO user_groups (name, owner_id) VALUES (?, ?)" + _RETURNING,
            (name, user_id),
        )
        group_id = cur.lastrowid
        conn.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id),
        )
        conn.commit()
        group = dict(conn.execute(
            "SELECT * FROM user_groups WHERE id = ?", (group_id,)
        ).fetchone())
    finally:
        conn.close()

    return jsonify(group), 201


# ── API: グループ詳細 / 削除 ───────────────────────────────────────────────────
@app.route("/api/groups/<int:group_id>", methods=["GET"])
@login_required
def api_get_group(group_id: int):
    user_id = session["user_id"]
    conn = get_db()
    try:
        group = conn.execute(
            "SELECT * FROM user_groups WHERE id = ?", (group_id,)
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404

        member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not member:
            return jsonify({"error": "Forbidden"}), 403

        members = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.picture_url, gm.joined_at
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = ?
            """,
            (group_id,),
        ).fetchall()

        shared = conn.execute(
            """
            SELECT sl.id, sl.owner_user_id, sl.collection_name, sl.created_at,
                   u.name AS owner_name
            FROM shared_lists sl
            JOIN users u ON u.id = sl.owner_user_id
            WHERE sl.group_id = ?
            """,
            (group_id,),
        ).fetchall()

        result = dict(group)
        result["is_owner"] = group["owner_id"] == user_id
        result["members"] = [dict(m) for m in members]
        result["shared_lists"] = [dict(s) for s in shared]
    finally:
        conn.close()

    return jsonify(result)


@app.route("/api/groups/<int:group_id>", methods=["DELETE"])
@login_required
def api_delete_group(group_id: int):
    user_id = session["user_id"]
    conn = get_db()
    try:
        group = conn.execute(
            "SELECT * FROM user_groups WHERE id = ?", (group_id,)
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404
        if group["owner_id"] != user_id:
            return jsonify({"error": "Forbidden: only owner can delete group"}), 403

        conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM invite_links WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM shared_lists WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM user_groups WHERE id = ?", (group_id,))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


# ── API: 招待リンク 生成 ───────────────────────────────────────────────────────
@app.route("/api/groups/<int:group_id>/invite", methods=["POST"])
@login_required
def api_create_invite(group_id: int):
    user_id = session["user_id"]
    conn = get_db()
    try:
        member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not member:
            return jsonify({"error": "Forbidden"}), 403

        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        conn.execute(
            "INSERT INTO invite_links (token, group_id, created_by, expires_at) VALUES (?, ?, ?, ?)",
            (token, group_id, user_id, expires_at),
        )
        conn.commit()
    finally:
        conn.close()

    invite_url = f"{APP_URL}/join/{token}"
    return jsonify({"token": token, "invite_url": invite_url, "expires_at": expires_at})


# ── API: 招待リンク 参照 ───────────────────────────────────────────────────────
@app.route("/api/invite/<token>", methods=["GET"])
def api_get_invite(token: str):
    conn = get_db()
    try:
        invite = conn.execute(
            "SELECT * FROM invite_links WHERE token = ?", (token,)
        ).fetchone()
        if not invite:
            return jsonify({"error": "Invalid token"}), 404

        if invite["expires_at"]:
            expires = datetime.fromisoformat(invite["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                return jsonify({"error": "Token expired"}), 410

        group = conn.execute(
            "SELECT id, name FROM user_groups WHERE id = ?", (invite["group_id"],)
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404

        group_id = group["id"]
        group_name = group["name"]
        expires_at = invite["expires_at"]
    finally:
        conn.close()

    return jsonify({"group_id": group_id, "group_name": group_name, "expires_at": expires_at})


# ── API: 招待リンク 承認 ───────────────────────────────────────────────────────
@app.route("/api/invite/<token>/accept", methods=["POST"])
@login_required
def api_accept_invite(token: str):
    user_id = session["user_id"]
    conn = get_db()
    try:
        invite = conn.execute(
            "SELECT * FROM invite_links WHERE token = ?", (token,)
        ).fetchone()
        if not invite:
            return jsonify({"error": "Invalid token"}), 404

        if invite["expires_at"]:
            expires = datetime.fromisoformat(invite["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                return jsonify({"error": "Token expired"}), 410

        group_id = invite["group_id"]
        group = conn.execute(
            "SELECT id, name FROM user_groups WHERE id = ?", (group_id,)
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404

        group_id_val = group["id"]
        group_name_val = group["name"]

        existing = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
                (group_id, user_id),
            )
            conn.execute(
                "UPDATE invite_links SET used_count = used_count + 1 WHERE token = ?",
                (token,),
            )
            conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True, "group_id": group_id_val, "group_name": group_name_val})


# ── API: グループメンバー削除 ──────────────────────────────────────────────────
@app.route("/api/groups/<int:group_id>/members/<int:target_user_id>", methods=["DELETE"])
@login_required
def api_remove_member(group_id: int, target_user_id: int):
    user_id = session["user_id"]
    conn = get_db()
    try:
        group = conn.execute(
            "SELECT * FROM user_groups WHERE id = ?", (group_id,)
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404

        is_owner = group["owner_id"] == user_id
        is_self = target_user_id == user_id

        if not is_owner and not is_self:
            return jsonify({"error": "Forbidden"}), 403

        conn.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, target_user_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


# ── API: 共有リスト 追加 ───────────────────────────────────────────────────────
@app.route("/api/groups/<int:group_id>/shared-lists", methods=["POST"])
@login_required
def api_add_shared_list(group_id: int):
    user_id = session["user_id"]
    data = request.get_json(force=True, silent=True) or {}
    collection_name = (data.get("collection_name") or "").strip()
    if not collection_name:
        return jsonify({"error": "collection_name is required"}), 400

    conn = get_db()
    try:
        member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        ).fetchone()
        if not member:
            return jsonify({"error": "Forbidden"}), 403

        try:
            cur = conn.execute(
                "INSERT INTO shared_lists (group_id, owner_user_id, collection_name)"
                " VALUES (?, ?, ?)" + _RETURNING,
                (group_id, user_id, collection_name),
            )
            conn.commit()
            sl = dict(conn.execute(
                "SELECT * FROM shared_lists WHERE id = ?", (cur.lastrowid,)
            ).fetchone())
        except _IntegrityError:
            if _USE_PG:
                conn.rollback()
            return jsonify({"error": "Already shared"}), 409
    finally:
        conn.close()

    return jsonify(sl), 201


# ── API: 共有リスト 削除 ───────────────────────────────────────────────────────
@app.route("/api/groups/<int:group_id>/shared-lists/<int:list_id>", methods=["DELETE"])
@login_required
def api_remove_shared_list(group_id: int, list_id: int):
    user_id = session["user_id"]
    conn = get_db()
    try:
        sl = conn.execute(
            "SELECT * FROM shared_lists WHERE id = ? AND group_id = ?",
            (list_id, group_id),
        ).fetchone()
        if not sl:
            return jsonify({"error": "Shared list not found"}), 404

        group = conn.execute(
            "SELECT owner_id FROM user_groups WHERE id = ?", (group_id,)
        ).fetchone()
        if not group:
            return jsonify({"error": "Group not found"}), 404

        is_list_owner = sl["owner_user_id"] == user_id
        is_group_owner = group["owner_id"] == user_id

        if not is_list_owner and not is_group_owner:
            return jsonify({"error": "Forbidden"}), 403

        conn.execute("DELETE FROM shared_lists WHERE id = ?", (list_id,))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


# ── 公式サイトから SNS リンクをスクレイプ ─────────────────────────────────────
_IG_SKIP  = {"p","reel","reels","explore","stories","tv","accounts","about","privacy","legal","help","press","_u","_n"}
_TW_SKIP  = {"intent","search","i","share","hashtag","home","login","settings","oauth","en","ja"}

def _scrape_social_links(website_url: str):
    """公式サイトの HTML から X/Twitter・Instagram 公式プロフィール URL を抽出する。"""
    try:
        req = urllib.request.Request(
            website_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; InfoBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read(200_000).decode("utf-8", errors="replace")
    except Exception:
        return None, None

    twitter_url = None
    for m in re.finditer(
        r'https?://(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,50})(?:[/?#"\'<\s]|$)',
        html,
    ):
        username = m.group(1).lower()
        if username not in _TW_SKIP:
            twitter_url = f"https://x.com/{m.group(1)}"
            break

    instagram_url = None
    for m in re.finditer(
        r'https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,50})(?:[/?#"\'<\s]|$)',
        html,
    ):
        username = m.group(1).lower()
        if username not in _IG_SKIP:
            instagram_url = f"https://www.instagram.com/{m.group(1)}/"
            break

    return twitter_url, instagram_url


# ── Google Places API: 店舗情報取得 ───────────────────────────────────────────
def _fetch_place_info(loc_id: int) -> dict:
    """Google Places API (New) でお店情報を取得し locations テーブルを更新する。"""
    if not GOOGLE_MAPS_API_KEY:
        return {}
    conn = get_db()
    try:
        loc = conn.execute(
            "SELECT id, shop_name, address, prefecture FROM locations WHERE id = ?",
            (loc_id,),
        ).fetchone()
        if not loc:
            return {}

        shop_name = loc["shop_name"] or ""
        address   = loc["address"] or loc["prefecture"] or ""
        query     = f"{shop_name} {address}".strip()
        if not query:
            return {}

        body = json.dumps(
            {"textQuery": query, "languageCode": "ja", "maxResultCount": 1},
            ensure_ascii=False,
        ).encode()
        field_mask = (
            "places.id,places.rating,places.userRatingCount,"
            "places.regularOpeningHours,places.paymentOptions,places.parkingOptions,"
            "places.websiteUri"
        )
        req = urllib.request.Request(
            "https://places.googleapis.com/v1/places:searchText",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
                "X-Goog-FieldMask": field_mask,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        now = datetime.now(timezone.utc).isoformat()
        places = data.get("places", [])
        if not places:
            conn.execute(
                "UPDATE locations SET place_info_fetched=1, place_info_fetched_at=? WHERE id=?",
                (now, loc_id),
            )
            conn.commit()
            return {"place_info_fetched_at": now}

        place = places[0]
        place_id             = place.get("id")
        google_rating        = place.get("rating")
        google_ratings_total = place.get("userRatingCount")
        website_url          = place.get("websiteUri")

        hours_obj      = place.get("regularOpeningHours") or {}
        bh_list        = hours_obj.get("weekdayDescriptions", [])
        business_hours = json.dumps(bh_list, ensure_ascii=False)

        payment_obj  = place.get("paymentOptions") or {}
        payment_list = []
        if payment_obj.get("acceptsCreditCards"): payment_list.append("クレジットカード")
        if payment_obj.get("acceptsDebitCards"):  payment_list.append("デビットカード")
        if payment_obj.get("acceptsNfc"):         payment_list.append("電子マネー")
        if payment_obj.get("acceptsCashOnly"):    payment_list.append("現金のみ")
        payment_methods = json.dumps(payment_list, ensure_ascii=False)

        parking_obj = place.get("parkingOptions") or {}
        has_parking = None
        if parking_obj:
            has_parking = 1 if any([
                parking_obj.get("freeParkingLot"),
                parking_obj.get("paidParkingLot"),
                parking_obj.get("freeGarageParking"),
                parking_obj.get("paidGarageParking"),
                parking_obj.get("valetParking"),
            ]) else 0

        # 公式サイトから SNS リンクをスクレイプ（既存の手動設定を上書きしない）
        existing = conn.execute(
            "SELECT official_twitter_url, official_instagram_url FROM locations WHERE id=?",
            (loc_id,),
        ).fetchone()
        official_twitter   = (existing["official_twitter_url"]   if existing else None)
        official_instagram = (existing["official_instagram_url"] if existing else None)

        if website_url and (not official_twitter or not official_instagram):
            scraped_tw, scraped_ig = _scrape_social_links(website_url)
            if not official_twitter:   official_twitter   = scraped_tw
            if not official_instagram: official_instagram = scraped_ig

        conn.execute(
            """UPDATE locations SET
               google_place_id=?, business_hours=?, google_rating=?,
               google_ratings_total=?, payment_methods=?, has_parking=?,
               website_url=?, official_twitter_url=?, official_instagram_url=?,
               place_info_fetched=1, place_info_fetched_at=?
               WHERE id=?""",
            (place_id, business_hours, google_rating, google_ratings_total,
             payment_methods, has_parking,
             website_url, official_twitter, official_instagram,
             now, loc_id),
        )
        conn.commit()
        return {
            "business_hours":        bh_list,
            "google_rating":         google_rating,
            "google_ratings_total":  google_ratings_total,
            "payment_methods":       payment_list,
            "has_parking":           has_parking,
            "website_url":           website_url,
            "official_twitter_url":  official_twitter,
            "official_instagram_url":official_instagram,
            "place_info_fetched_at": now,
        }
    except urllib.error.HTTPError as e:
        print(f"[place-info] HTTP {e.code} for loc {loc_id}: {e.reason}")
        return {}
    except Exception as e:
        print(f"[place-info] Error for loc {loc_id}: {e}")
        return {}
    finally:
        conn.close()


def _fetch_all_place_info_background() -> None:
    """起動後バックグラウンドで未取得ロケーション全件の店舗情報を取得する。"""
    if not GOOGLE_MAPS_API_KEY:
        return

    def _worker():
        time.sleep(3)
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id FROM locations WHERE COALESCE(place_info_fetched,0)=0"
            ).fetchall()
            ids = [r["id"] for r in rows]
        finally:
            conn.close()
        if not ids:
            return
        print(f"[place-info] {len(ids)} 件のお店情報を取得します…")
        for loc_id in ids:
            _fetch_place_info(loc_id)
            time.sleep(0.5)
        print("[place-info] 取得完了")

    threading.Thread(target=_worker, daemon=True).start()


# ── 重複ロケーション統合（起動時） ────────────────────────────────────────────
def _dedup_locations_on_startup() -> int:
    """shop_name が重複するロケーションを統合する。レビューが多い方 → id が大きい方を優先。"""
    from collections import defaultdict
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT l.id, l.shop_name,
                   (SELECT COUNT(*) FROM visits WHERE location_id = l.id) AS vc
            FROM locations l
            WHERE l.shop_name IS NOT NULL AND l.shop_name != ''
            ORDER BY l.shop_name,
                     (SELECT COUNT(*) FROM visits WHERE location_id = l.id) DESC,
                     l.id DESC
            """
        ).fetchall()

        groups = defaultdict(list)
        for r in rows:
            groups[r["shop_name"].strip()].append(r["id"])

        deleted = 0
        for ids in groups.values():
            if len(ids) <= 1:
                continue
            winner_id, loser_ids = ids[0], ids[1:]
            ph = ",".join("?" * len(loser_ids))
            conn.execute(
                f"UPDATE visits SET location_id=? WHERE location_id IN ({ph})",
                [winner_id] + loser_ids,
            )
            conn.execute(
                f"UPDATE visit_images SET location_id=? WHERE location_id IN ({ph}) AND visit_id IS NULL",
                [winner_id] + loser_ids,
            )
            conn.execute(f"DELETE FROM locations WHERE id IN ({ph})", loser_ids)
            deleted += len(loser_ids)

        if deleted:
            conn.commit()
        return deleted
    finally:
        conn.close()


# ── 起動時初期化 (gunicorn / 直接実行の両方で動作) ────────────────────────────
try:
    init_db()
    _fetch_all_place_info_background()
except Exception as _startup_err:
    print(f"[startup] 初期化エラー: {_startup_err}")

# ── エントリポイント (ローカル開発用) ────────────────────────────────────────────
if __name__ == "__main__":
    removed = _dedup_locations_on_startup()
    if removed:
        print(f"重複ロケーション {removed} 件を統合しました")
    print("サーバー起動: http://localhost:8000")
    print("マップ:   http://localhost:8000/")
    print("リスト:   http://localhost:8000/list")
    print("グループ: http://localhost:8000/groups")
    print("停止するには Ctrl+C")
    app.run(host="0.0.0.0", port=8000, debug=True)
