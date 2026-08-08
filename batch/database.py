import json
import os
import re
from datetime import datetime
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL")
_USE_PG = bool(DATABASE_URL)

if _USE_PG:
    import psycopg2

    def _get_conn():
        return psycopg2.connect(DATABASE_URL)

    def _adapt(sql: str) -> str:
        """SQLite の ? プレースホルダと INSERT OR IGNORE を PostgreSQL 向けに変換する。"""
        sql = sql.replace("?", "%s")
        if re.search(r'\bINSERT\s+OR\s+IGNORE\b', sql, re.IGNORECASE):
            sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\b', 'INSERT', sql, re.IGNORECASE)
            sql = sql.rstrip(';') + ' ON CONFLICT DO NOTHING'
        return sql

    def _rows_to_dicts(rows, keys):
        return [{k: r[i] for i, k in enumerate(keys)} for r in rows]

else:
    import sqlite3
    DB_PATH = Path(__file__).parent.parent / "instagram_map.db"

    def _get_conn():
        return sqlite3.connect(DB_PATH)

    def _adapt(sql: str) -> str:
        return sql

    def _rows_to_dicts(rows, keys):
        return [{k: r[i] for i, k in enumerate(keys)} for r in rows]


LOCATIONS_JSON_PATH = Path(__file__).parent.parent / "data" / "locations.json"


def _execute(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(_adapt(sql), params)
    return cur


def _executemany(conn, sql, params_list):
    cur = conn.cursor()
    cur.executemany(_adapt(sql), params_list)
    return cur


def _add_column_if_missing(cur, table: str, col_def: str):
    """ALTER TABLE ADD COLUMN を安全に実行する（既存列は無視）。"""
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    except Exception:
        pass


def init_db():
    conn = _get_conn()
    try:
        cur = conn.cursor()
        if _USE_PG:
            cur.execute("""
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
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
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
            cur.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    id SERIAL PRIMARY KEY,
                    post_id INTEGER NOT NULL,
                    shop_name TEXT,
                    address TEXT,
                    prefecture TEXT,
                    city TEXT,
                    lat REAL,
                    lng REAL,
                    genre TEXT,
                    recommended_menus TEXT,
                    is_geocoded INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    google_rating REAL,
                    google_ratings_total INTEGER,
                    business_hours TEXT,
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
            # ── 新規テーブル (PostgreSQL) ──────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    name TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS visits (
                    id SERIAL PRIMARY KEY,
                    loc_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    visited INTEGER DEFAULT 1,
                    rating INTEGER DEFAULT 0,
                    impression TEXT,
                    want_again INTEGER DEFAULT 0,
                    next_comment TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (loc_id) REFERENCES locations(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS visit_images (
                    id SERIAL PRIMARY KEY,
                    visit_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (visit_id) REFERENCES visits(id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    joined_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS group_invites (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS group_shared_lists (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    collection_name TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            """)
            # 既存テーブルへのカラム追加
            _add_column_if_missing(cur, "saved_posts",   "user_id TEXT")
            _add_column_if_missing(cur, "group_members", "role TEXT DEFAULT 'guest'")
            _add_column_if_missing(cur, "group_invites", "role TEXT DEFAULT 'guest'")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS allowed_emails (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    added_by TEXT NOT NULL,
                    added_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        else:
            cur.execute("""
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS batch_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    total_saved INTEGER,
                    new_posts INTEGER,
                    processed INTEGER,
                    status TEXT,
                    message TEXT
                )
            """)
            cur.execute("""
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
                    google_rating REAL,
                    google_ratings_total INTEGER,
                    business_hours TEXT,
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
            # 既存データを locations テーブルへ移行
            cur.execute("""
                INSERT INTO locations (post_id, shop_name, address, prefecture, city, lat, lng, is_geocoded)
                SELECT id, shop_name, address, prefecture, city, lat, lng, is_geocoded
                FROM saved_posts
                WHERE address_found = 1
                  AND address IS NOT NULL
                  AND id NOT IN (SELECT DISTINCT post_id FROM locations)
            """)
            # ── 新規テーブル (SQLite) ──────────────────────────────────────────
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    name TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    loc_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    visited INTEGER DEFAULT 1,
                    rating INTEGER DEFAULT 0,
                    impression TEXT,
                    want_again INTEGER DEFAULT 0,
                    next_comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (loc_id) REFERENCES locations(id),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS visit_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visit_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (visit_id) REFERENCES visits(id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS group_invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS group_shared_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    collection_name TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            """)
            # 既存テーブルへのカラム追加（べき等）
            for col in [
                ("saved_posts",   "user_id TEXT"),
                ("group_members", "role TEXT DEFAULT 'guest'"),
                ("group_invites", "role TEXT DEFAULT 'guest'"),
                ("locations",   "genre TEXT"),
                ("locations",   "recommended_menus TEXT"),
                ("locations",   "google_rating REAL"),
                ("locations",   "google_ratings_total INTEGER"),
                ("locations",   "business_hours TEXT"),
                ("locations",   "payment_methods TEXT"),
                ("locations",   "has_parking INTEGER"),
                ("locations",   "website_url TEXT"),
                ("locations",   "official_twitter_url TEXT"),
                ("locations",   "official_instagram_url TEXT"),
                ("locations",   "place_info_fetched INTEGER DEFAULT 0"),
                ("locations",   "place_info_fetched_at TEXT"),
            ]:
                _add_column_if_missing(cur, col[0], col[1])

            cur.execute("""
                CREATE TABLE IF NOT EXISTS allowed_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    added_by TEXT NOT NULL,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # visits テーブルのスキーマ移行
            # 旧バージョンは location_id カラムを使用、新バージョンは loc_id を使用
            try:
                cur.execute("SELECT loc_id FROM visits LIMIT 0")
            except Exception:
                try:
                    cur.execute("DROP TABLE IF EXISTS visits_old")
                    cur.execute("ALTER TABLE visits RENAME TO visits_old")
                    cur.execute("""
                        CREATE TABLE visits (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            loc_id INTEGER NOT NULL,
                            user_id TEXT NOT NULL,
                            visited INTEGER DEFAULT 1,
                            rating INTEGER DEFAULT 0,
                            impression TEXT,
                            want_again INTEGER DEFAULT 0,
                            next_comment TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (loc_id) REFERENCES locations(id),
                            FOREIGN KEY (user_id) REFERENCES users(id)
                        )
                    """)
                    # 旧データを新スキーマへコピー（location_id → loc_id）
                    try:
                        cur.execute("""
                            INSERT INTO visits
                                (id, loc_id, user_id, visited, rating, impression,
                                 want_again, next_comment, updated_at)
                            SELECT id, location_id, user_id, visited, rating, impression,
                                   want_again, next_comment, updated_at
                            FROM visits_old
                        """)
                    except Exception:
                        pass  # 旧データの移行に失敗しても新テーブルはそのまま使用
                    cur.execute("DROP TABLE IF EXISTS visits_old")
                except Exception as mig_err:
                    import logging as _log
                    _log.getLogger(__name__).warning(f"visits マイグレーション失敗: {mig_err}")

            # users.id スキーマ移行（旧 INTEGER PRIMARY KEY → TEXT PRIMARY KEY）
            # Google user ID（20桁）は SQLite INTEGER（64bit）に収まらないため TEXT が必要
            try:
                cur.execute("PRAGMA table_info(users)")
                users_col_type = {r[1]: r[2].upper() for r in cur.fetchall()}.get("id", "TEXT")
                if users_col_type not in ("TEXT", "VARCHAR", "CHAR"):
                    import logging as _log
                    _log.getLogger(__name__).info("users.id を INTEGER→TEXT に移行します")
                    cur.execute("DROP TABLE IF EXISTS users_old")
                    cur.execute("ALTER TABLE users RENAME TO users_old")
                    cur.execute("""
                        CREATE TABLE users (
                            id TEXT PRIMARY KEY,
                            email TEXT,
                            name TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cur.execute("""
                        INSERT INTO users (id, email, name, created_at)
                        SELECT CAST(id AS TEXT), email, name, created_at FROM users_old
                    """)
                    cur.execute("DROP TABLE IF EXISTS users_old")
            except Exception as mig_err:
                import logging as _log
                _log.getLogger(__name__).warning(f"users スキーマ移行失敗: {mig_err}")

            # saved_posts.user_id スキーマ移行（旧 INTEGER → TEXT）
            # INTEGER 列に Google ID を入れるとオーバーフローで REAL になり検索不一致が起きる
            try:
                cur.execute("PRAGMA table_info(saved_posts)")
                sp_uid_type = {r[1]: r[2].upper() for r in cur.fetchall()}.get("user_id", "TEXT")
                if sp_uid_type not in ("TEXT", "VARCHAR", "CHAR"):
                    import logging as _log
                    _log.getLogger(__name__).info("saved_posts.user_id を INTEGER→TEXT に移行します")
                    cur.execute("DROP TABLE IF EXISTS saved_posts_old")
                    cur.execute("ALTER TABLE saved_posts RENAME TO saved_posts_old")
                    cur.execute("""
                        CREATE TABLE saved_posts (
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
                            user_id TEXT
                        )
                    """)
                    # REAL/INTEGER で保存された user_id は精度が失われているので NULL にリセット
                    # ensure_user の移行処理で正しい Google ID が後から設定される
                    cur.execute("""
                        INSERT INTO saved_posts (id, instagram_url, instagram_shortcode, caption,
                            shop_name, address, prefecture, city, lat, lng, address_found,
                            is_geocoded, ig_saved_at, processed_at, created_at, user_id)
                        SELECT id, instagram_url, instagram_shortcode, caption,
                               shop_name, address, prefecture, city, lat, lng, address_found,
                               is_geocoded, ig_saved_at, processed_at, created_at,
                               CASE WHEN typeof(user_id) IN ('real', 'integer') THEN NULL
                                    ELSE user_id END
                        FROM saved_posts_old
                    """)
                    cur.execute("DROP TABLE IF EXISTS saved_posts_old")
            except Exception as mig_err:
                import logging as _log
                _log.getLogger(__name__).warning(f"saved_posts スキーマ移行失敗: {mig_err}")

        # env var から許可メールをシード（テーブルが空のときのみ）
        _env_emails = [e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()]
        if _env_emails:
            _cnt = _execute(conn, "SELECT COUNT(*) FROM allowed_emails").fetchone()[0]
            if _cnt == 0:
                for _em in _env_emails:
                    try:
                        _execute(conn, "INSERT OR IGNORE INTO allowed_emails (email, added_by) VALUES (?, ?)", (_em, "env"))
                    except Exception:
                        pass

        conn.commit()
    finally:
        conn.close()


def get_known_urls(user_id: str = None):
    conn = _get_conn()
    try:
        if user_id:
            cur = _execute(conn, "SELECT instagram_url FROM saved_posts WHERE user_id = ?", (user_id,))
        else:
            cur = _execute(conn, "SELECT instagram_url FROM saved_posts")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def insert_new_posts(posts, user_id: str = None):
    conn = _get_conn()
    try:
        _executemany(
            conn,
            "INSERT OR IGNORE INTO saved_posts"
            " (instagram_url, instagram_shortcode, caption, ig_saved_at, user_id)"
            " VALUES (?, ?, ?, ?, ?)",
            [(p["instagram_url"], p.get("instagram_shortcode"),
              p.get("caption", ""), p.get("ig_saved_at"), user_id) for p in posts],
        )
        conn.commit()
    finally:
        conn.close()


def get_unprocessed_posts(user_id: str = None):
    conn = _get_conn()
    try:
        if user_id:
            cur = _execute(
                conn,
                "SELECT id, instagram_url, instagram_shortcode, caption"
                " FROM saved_posts WHERE address_found = 0 AND user_id = ?",
                (user_id,),
            )
        else:
            cur = _execute(
                conn,
                "SELECT id, instagram_url, instagram_shortcode, caption"
                " FROM saved_posts WHERE address_found = 0",
            )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"id": r[0], "instagram_url": r[1], "instagram_shortcode": r[2],
             "caption": r[3] or ""} for r in rows]


def update_processed(post_id, found):
    address_found = 1 if found else 2
    conn = _get_conn()
    try:
        _execute(
            conn,
            "UPDATE saved_posts SET address_found = ?, processed_at = ? WHERE id = ?",
            (address_found, datetime.now().isoformat(), post_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_locations(post_id, shops):
    """1投稿から抽出した複数店舗を locations テーブルに登録する。
    同一ユーザーの同名・同住所の店舗は重複挿入しない（全角/半角の違いも吸収）。
    """
    conn = _get_conn()
    try:
        # 同一ユーザーの既存 locations を先に取得して正規化済みセットを作る
        existing_cur = _execute(conn, """
            SELECT l.shop_name, l.address FROM locations l
            JOIN saved_posts p  ON l.post_id  = p.id
            JOIN saved_posts p2 ON p2.id = ?
            WHERE p.user_id = p2.user_id
              AND l.shop_name IS NOT NULL AND l.address IS NOT NULL
        """, (post_id,))
        existing_norm = {
            (_normalize_text(r[0]), _normalize_text(r[1]))
            for r in existing_cur.fetchall()
        }

        for s in shops:
            shop_name = s.get("shop_name")
            address   = s.get("address")

            # 正規化した上で既存チェック（全角/半角・ダッシュ種別を吸収）
            if shop_name and address:
                if (_normalize_text(shop_name), _normalize_text(address)) in existing_norm:
                    continue

            _execute(
                conn,
                "INSERT INTO locations"
                " (post_id, shop_name, address, prefecture, city, genre, recommended_menus)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    post_id,
                    shop_name,
                    address,
                    s.get("prefecture"),
                    s.get("city"),
                    s.get("genre"),
                    json.dumps(s.get("recommended_menus") or [], ensure_ascii=False),
                ),
            )
            # 追加したレコードも即座にセットへ反映（同一バッチ内での重複も防ぐ）
            if shop_name and address:
                existing_norm.add((_normalize_text(shop_name), _normalize_text(address)))

        conn.commit()
    finally:
        conn.close()


def _normalize_text(text: str) -> str:
    """全角→半角変換（NFKC）＋各種ダッシュ・ハイフンを半角ハイフンに統一する。"""
    import unicodedata
    if not text:
        return text
    text = unicodedata.normalize("NFKC", text)
    # 全角ハイフン(FF0D)、マイナス記号(2212)、各種ダッシュ類 → 半角ハイフン
    for ch in "－−–—―‐‑‒":
        text = text.replace(ch, "-")
    return text.strip()


def normalize_duplicate_locations(user_id: str) -> int:
    """shop_name と address が同じ locations を1件に統合する。
    visits は最小 id の loc_id に付け替え、重複レコードを削除する。
    正規化は全角/半角・ダッシュ種別の違いを吸収して比較する。
    統合した重複件数を返す。
    """
    import logging as _log
    from collections import defaultdict
    _logger = _log.getLogger(__name__)

    conn = _get_conn()
    merged = 0
    try:
        # ユーザーの全 location を取得
        cur = _execute(conn, """
            SELECT l.id, l.shop_name, l.address
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            WHERE p.user_id = ?
              AND l.shop_name IS NOT NULL
              AND l.address   IS NOT NULL
        """, (user_id,))
        all_locs = cur.fetchall()

        # 正規化キー（全角→半角変換済み）でグループ化
        groups = defaultdict(list)
        for loc_id, shop_name, address in all_locs:
            key = (_normalize_text(shop_name), _normalize_text(address))
            groups[key].append(loc_id)

        for (norm_name, norm_addr), ids in groups.items():
            if len(ids) <= 1:
                continue
            keep_id = min(ids)
            dup_ids = [i for i in ids if i != keep_id]
            for dup_id in dup_ids:
                _execute(conn, "UPDATE visits SET loc_id = ? WHERE loc_id = ?", (keep_id, dup_id))
                _execute(conn, "DELETE FROM locations WHERE id = ?", (dup_id,))
                merged += 1
                _logger.info(f"  重複統合: '{norm_name}' loc_id={dup_id} → {keep_id}")

        conn.commit()
    finally:
        conn.close()

    return merged


def get_ungeocoded_locations():
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "SELECT id, address FROM locations WHERE is_geocoded = 0 AND address IS NOT NULL",
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"id": r[0], "address": r[1]} for r in rows]


def update_location_geocoded(loc_id, lat, lng):
    conn = _get_conn()
    try:
        _execute(
            conn,
            "UPDATE locations SET lat = ?, lng = ?, is_geocoded = 1 WHERE id = ?",
            (lat, lng, loc_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_geocoded(post_id, lat, lng):
    """後方互換用: saved_posts の geocoding 更新（旧コードから呼ばれる場合のみ）。"""
    conn = _get_conn()
    try:
        _execute(
            conn,
            "UPDATE saved_posts SET lat = ?, lng = ?, is_geocoded = 1 WHERE id = ?",
            (lat, lng, post_id),
        )
        conn.commit()
    finally:
        conn.close()


def log_batch(total_saved, new_posts, processed, status, message=""):
    conn = _get_conn()
    try:
        _execute(
            conn,
            "INSERT INTO batch_log (total_saved, new_posts, processed, status, message)"
            " VALUES (?, ?, ?, ?, ?)",
            (total_saved, new_posts, processed, status, message),
        )
        conn.commit()
    finally:
        conn.close()


def export_locations_json():
    """Geocoding 済みの全 locations を JSON に出力する。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            """SELECT p.instagram_url, l.shop_name, l.address, l.prefecture, l.city,
                      l.lat, l.lng, l.genre, l.recommended_menus
               FROM locations l
               JOIN saved_posts p ON l.post_id = p.id
               WHERE l.is_geocoded = 1
               ORDER BY l.prefecture, l.city, l.shop_name""",
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    locations = [
        {
            "instagram_url": r[0],
            "shop_name": r[1],
            "address": r[2],
            "prefecture": r[3],
            "city": r[4],
            "lat": r[5],
            "lng": r[6],
            "genre": r[7],
            "recommended_menus": json.loads(r[8]) if r[8] else [],
        }
        for r in rows
    ]

    LOCATIONS_JSON_PATH.parent.mkdir(exist_ok=True)
    with open(LOCATIONS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(locations, f, ensure_ascii=False, indent=2)

    return len(locations)


# ══════════════════════════════════════════════════════════════════════════════
# マルチユーザー対応の追加関数
# ══════════════════════════════════════════════════════════════════════════════

def ensure_user(user_id: str, email: str, name: str):
    """Google ログイン時にユーザーレコードを作成 or 更新する。
    旧バッチで生成された古いIDのレコードがあれば Google ID へ自動移行する。
    """
    import logging as _log
    _logger = _log.getLogger(__name__)

    conn = _get_conn()
    try:
        # 同メールで異なるID（旧システムの数値IDなど）が存在する場合は移行
        cur = _execute(conn, "SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
        old_row = cur.fetchone()
        if old_row:
            old_id = old_row[0]
            _logger.info(f"旧ユーザーID '{old_id}' → 新ID '{user_id}' へ移行します")
            # user_id が旧ID、または型移行でNULLになったレコードをまとめて更新
            _execute(conn, "UPDATE saved_posts SET user_id = ? WHERE user_id = ? OR user_id IS NULL", (user_id, old_id))
            _execute(conn, "UPDATE visits      SET user_id = ? WHERE user_id = ?", (user_id, old_id))
            _execute(conn, "DELETE FROM users WHERE id = ?", (old_id,))
        else:
            # NULLのuser_idも同一ユーザーの旧データとして更新（スキーマ移行後の復旧）
            _execute(conn, "UPDATE saved_posts SET user_id = ? WHERE user_id IS NULL", (user_id,))

        _execute(
            conn,
            "INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)",
            (user_id, email, name),
        )
        _execute(
            conn,
            "UPDATE users SET email = ?, name = ? WHERE id = ?",
            (email, name, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def remove_group_member(group_id: int, target_user_id: str, requesting_user_id: str) -> bool:
    """オーナーまたは管理者メンバーが他のメンバーを削除する（オーナーは削除不可）。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT owner_user_id FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        if not row:
            return False
        owner_id = row[0]
        if target_user_id == owner_id:
            return False
        is_owner = requesting_user_id == owner_id
        if not is_owner:
            admin_cur = _execute(conn,
                "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ? AND role = 'admin'",
                (group_id, requesting_user_id))
            if not admin_cur.fetchone():
                return False
        cur = _execute(conn,
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, target_user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def leave_group(group_id: int, user_id: str) -> bool:
    """メンバーがグループから退会する（オーナーは退会不可 — グループ削除を使用）。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT owner_user_id FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        if not row or row[0] == user_id:
            return False
        cur = _execute(conn,
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_user_name(user_id: str) -> str:
    """users テーブルからユーザー名を返す。見つからない場合は空文字。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT name FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


def get_location_owner(loc_id: int):
    """locations.id から所有ユーザー ID を返す。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "SELECT p.user_id FROM locations l"
            " JOIN saved_posts p ON l.post_id = p.id"
            " WHERE l.id = ?",
            (loc_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_location_by_id(loc_id: int):
    """単一 location を dict で返す。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "SELECT l.id, p.instagram_url, l.shop_name, l.address, l.prefecture, l.city,"
            "       l.lat, l.lng, l.genre, l.recommended_menus,"
            "       l.google_rating, l.google_ratings_total, l.business_hours,"
            "       l.payment_methods, l.has_parking,"
            "       l.website_url, l.official_twitter_url, l.official_instagram_url,"
            "       l.place_info_fetched, l.place_info_fetched_at"
            " FROM locations l"
            " JOIN saved_posts p ON l.post_id = p.id"
            " WHERE l.id = ?",
            (loc_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return _loc_row_to_dict(row)


def _loc_row_to_dict(row):
    return {
        "id":                    row[0],
        "instagram_url":         row[1],
        "shop_name":             row[2],
        "address":               row[3],
        "prefecture":            row[4],
        "city":                  row[5],
        "lat":                   row[6],
        "lng":                   row[7],
        "genre":                 row[8],
        "recommended_menus":     json.loads(row[9]) if row[9] else [],
        "google_rating":         row[10],
        "google_ratings_total":  row[11],
        "business_hours":        json.loads(row[12]) if row[12] else None,
        "payment_methods":       json.loads(row[13]) if row[13] else None,
        "has_parking":           row[14],
        "website_url":           row[15],
        "official_twitter_url":  row[16],
        "official_instagram_url":row[17],
        "place_info_fetched":    row[18],
        "place_info_fetched_at": row[19],
    }


def get_locations_for_user(user_id: str) -> list:
    """ユーザーの geocoding 済み locations を、最新の自分の訪問情報とともに返す。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            """
            SELECT l.id, p.instagram_url, l.shop_name, l.address, l.prefecture, l.city,
                   l.lat, l.lng, l.genre, l.recommended_menus,
                   l.google_rating, l.google_ratings_total, l.business_hours,
                   l.payment_methods, l.has_parking,
                   l.website_url, l.official_twitter_url, l.official_instagram_url,
                   l.place_info_fetched, l.place_info_fetched_at,
                   (SELECT visited    FROM visits WHERE loc_id = l.id AND user_id = ? ORDER BY updated_at DESC LIMIT 1) AS visited,
                   (SELECT rating     FROM visits WHERE loc_id = l.id AND user_id = ? ORDER BY updated_at DESC LIMIT 1) AS rating,
                   (SELECT want_again FROM visits WHERE loc_id = l.id AND user_id = ? ORDER BY updated_at DESC LIMIT 1) AS want_again
            FROM locations l
            JOIN saved_posts p ON l.post_id = p.id
            WHERE p.user_id = ? AND l.is_geocoded = 1
            ORDER BY l.prefecture, l.city, l.shop_name
            """,
            (user_id, user_id, user_id, user_id),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        d = _loc_row_to_dict(row[:20])
        d["visited"]    = row[20] or 0
        d["rating"]     = row[21] or 0
        d["want_again"] = row[22] or 0
        d["source"]     = "own"
        result.append(d)
    return result


def get_locations_for_group(group_id: int, current_user_id: str) -> list:
    """グループの共有リストに登録されたロケーション一覧を返す（現在ユーザーの訪問情報付き）。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, """
            SELECT DISTINCT
                   l.id, p.instagram_url, l.shop_name, l.address, l.prefecture, l.city,
                   l.lat, l.lng, l.genre, l.recommended_menus,
                   l.google_rating, l.google_ratings_total, l.business_hours,
                   l.payment_methods, l.has_parking,
                   l.website_url, l.official_twitter_url, l.official_instagram_url,
                   l.place_info_fetched, l.place_info_fetched_at,
                   (SELECT visited    FROM visits WHERE loc_id = l.id AND user_id = ? ORDER BY updated_at DESC LIMIT 1),
                   (SELECT rating     FROM visits WHERE loc_id = l.id AND user_id = ? ORDER BY updated_at DESC LIMIT 1),
                   (SELECT want_again FROM visits WHERE loc_id = l.id AND user_id = ? ORDER BY updated_at DESC LIMIT 1),
                   p.user_id AS owner_user_id,
                   u.name    AS owner_name
            FROM locations l
            JOIN saved_posts p        ON l.post_id       = p.id
            JOIN users u              ON p.user_id        = u.id
            JOIN group_shared_lists gsl
              ON gsl.owner_user_id = p.user_id AND gsl.group_id = ?
            WHERE l.is_geocoded = 1
              AND (gsl.collection_name = '__all__' OR gsl.collection_name = l.prefecture)
            ORDER BY l.prefecture, l.city, l.shop_name
        """, (current_user_id, current_user_id, current_user_id, group_id))
        rows = cur.fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        d = _loc_row_to_dict(row[:20])
        d["visited"]       = row[20] or 0
        d["rating"]        = row[21] or 0
        d["want_again"]    = row[22] or 0
        d["owner_user_id"] = row[23]
        d["owner_name"]    = row[24]
        d["source"]        = "group"
        result.append(d)
    return result


def update_location_fields(loc_id: int, fields: dict):
    """genre / website_url 等を更新する。"""
    conn = _get_conn()
    try:
        for key, value in fields.items():
            _execute(conn, f"UPDATE locations SET {key} = ? WHERE id = ?", (value, loc_id))
        conn.commit()
    finally:
        conn.close()


def update_location_place_info(loc_id: int, data: dict):
    conn = _get_conn()
    try:
        _execute(
            conn,
            """UPDATE locations SET
                google_rating = ?, google_ratings_total = ?,
                business_hours = ?, payment_methods = ?, has_parking = ?,
                website_url = ?, place_info_fetched = 1, place_info_fetched_at = ?
               WHERE id = ?""",
            (
                data.get("google_rating"),
                data.get("google_ratings_total"),
                json.dumps(data["business_hours"], ensure_ascii=False) if data.get("business_hours") else None,
                json.dumps(data["payment_methods"], ensure_ascii=False) if data.get("payment_methods") else None,
                data.get("has_parking"),
                data.get("website_url"),
                data.get("place_info_fetched_at"),
                loc_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ── 訪問記録 ──────────────────────────────────────────────────────────────────

def create_visit_record(loc_id, user_id, visited, rating, impression, want_again, next_comment) -> int:
    conn = _get_conn()
    try:
        now = datetime.now().isoformat()
        cur = _execute(
            conn,
            "INSERT INTO visits (loc_id, user_id, visited, rating, impression, want_again, next_comment, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (loc_id, user_id, visited, rating, impression, want_again, next_comment, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_visits_for_location(loc_id: int, current_user_id: str) -> list:
    """location に紐づく全ユーザーの訪問記録を返す（is_own フラグ付き）。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            """
            SELECT v.id, u.name, v.user_id, v.visited, v.rating,
                   v.impression, v.want_again, v.next_comment, v.updated_at
            FROM visits v
            JOIN users u ON v.user_id = u.id
            WHERE v.loc_id = ?
            ORDER BY v.updated_at DESC
            """,
            (loc_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        visit_id = row[0]
        images   = _get_visit_images(visit_id)
        result.append({
            "id":           row[0],
            "user_name":    row[1],
            "is_own":       row[2] == current_user_id,
            "visited":      row[3],
            "rating":       row[4],
            "impression":   row[5] or "",
            "want_again":   row[6],
            "next_comment": row[7] or "",
            "updated_at":   row[8],
            "images":       images,
        })
    return result


def _get_visit_images(visit_id: int) -> list:
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT id, filename FROM visit_images WHERE visit_id = ?", (visit_id,))
        return [{"id": r[0], "filename": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def get_visit_by_id(visit_id: int, user_id: str):
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "SELECT id, loc_id, visited, rating, impression, want_again, next_comment, updated_at"
            " FROM visits WHERE id = ? AND user_id = ?",
            (visit_id, user_id),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    images = _get_visit_images(row[0])
    return {
        "id":           row[0],
        "loc_id":       row[1],
        "visited":      row[2],
        "rating":       row[3],
        "impression":   row[4] or "",
        "want_again":   row[5],
        "next_comment": row[6] or "",
        "updated_at":   row[7],
        "images":       images,
    }


def update_visit_record(visit_id: int, user_id: str, data: dict) -> bool:
    conn = _get_conn()
    try:
        now = datetime.now().isoformat()
        cur = _execute(
            conn,
            "UPDATE visits SET visited=?, rating=?, impression=?, want_again=?, next_comment=?, updated_at=?"
            " WHERE id=? AND user_id=?",
            (
                int(data.get("visited", 1)),
                int(data.get("rating", 0)),
                data.get("impression", ""),
                int(data.get("want_again", 0)),
                data.get("next_comment", ""),
                now,
                visit_id, user_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_visit_record(visit_id: int, user_id: str) -> bool:
    conn = _get_conn()
    try:
        _execute(conn, "DELETE FROM visit_images WHERE visit_id = ?", (visit_id,))
        cur = _execute(conn, "DELETE FROM visits WHERE id = ? AND user_id = ?", (visit_id, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def add_visit_image(visit_id: int, filename: str) -> int:
    conn = _get_conn()
    try:
        cur = _execute(conn, "INSERT INTO visit_images (visit_id, filename) VALUES (?, ?)", (visit_id, filename))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_visit_image_record(image_id: int, user_id: str):
    """画像レコードを削除してファイル名を返す（権限確認あり）。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "SELECT vi.filename FROM visit_images vi"
            " JOIN visits v ON vi.visit_id = v.id"
            " WHERE vi.id = ? AND v.user_id = ?",
            (image_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        _execute(conn, "DELETE FROM visit_images WHERE id = ?", (image_id,))
        conn.commit()
        return row[0]
    finally:
        conn.close()


# ── グループ ─────────────────────────────────────────────────────────────────

def get_groups_for_user(user_id: str) -> list:
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            """
            SELECT g.id, g.name, g.owner_user_id,
                   (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS member_count,
                   (SELECT COUNT(*) FROM group_shared_lists WHERE group_id = g.id) AS shared_count
            FROM groups g
            WHERE g.owner_user_id = ?
               OR g.id IN (SELECT group_id FROM group_members WHERE user_id = ?)
            ORDER BY g.created_at DESC
            """,
            (user_id, user_id),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "name": r[1], "is_owner": r[2] == user_id,
         "member_count": r[3], "shared_count": r[4]}
        for r in rows
    ]


def create_group_record(name: str, owner_user_id: str) -> int:
    conn = _get_conn()
    try:
        cur = _execute(conn, "INSERT INTO groups (name, owner_user_id) VALUES (?, ?)", (name, owner_user_id))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_group_detail(group_id: int, user_id: str):
    conn = _get_conn()
    try:
        # グループ基本情報
        cur = _execute(conn, "SELECT id, name, owner_user_id FROM groups WHERE id = ?", (group_id,))
        g = cur.fetchone()
        if not g:
            return None
        # メンバー確認
        cur = _execute(
            conn,
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )
        is_member = cur.fetchone() is not None
        if g[2] != user_id and not is_member:
            return None

        # メンバー一覧（role 付き）
        cur = _execute(
            conn,
            """SELECT u.id, u.name, u.email, gm.role FROM group_members gm
               JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?""",
            (group_id,),
        )
        members = [{"id": r[0], "name": r[1], "picture_url": None, "role": r[3] or "guest"} for r in cur.fetchall()]
        # オーナーも追加（オーナーは常に admin）
        cur = _execute(conn, "SELECT id, name FROM users WHERE id = ?", (g[2],))
        owner = cur.fetchone()
        if owner and not any(m["id"] == owner[0] for m in members):
            members.insert(0, {"id": owner[0], "name": owner[1], "picture_url": None, "role": "admin"})

        # 共有リスト
        cur = _execute(
            conn,
            """SELECT gsl.id, gsl.collection_name, gsl.owner_user_id, u.name
               FROM group_shared_lists gsl
               JOIN users u ON gsl.owner_user_id = u.id
               WHERE gsl.group_id = ?""",
            (group_id,),
        )
        shared_lists = [
            {"id": r[0], "collection_name": r[1], "owner_user_id": r[2], "owner_name": r[3]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()

    return {
        "id":           g[0],
        "name":         g[1],
        "owner_id":     g[2],
        "is_owner":     g[2] == user_id,
        "members":      members,
        "shared_lists": shared_lists,
    }


def delete_group_record(group_id: int, user_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT owner_user_id FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        if not row or row[0] != user_id:
            return False
        _execute(conn, "DELETE FROM group_shared_lists WHERE group_id = ?", (group_id,))
        _execute(conn, "DELETE FROM group_invites WHERE group_id = ?", (group_id,))
        _execute(conn, "DELETE FROM group_members WHERE group_id = ?", (group_id,))
        _execute(conn, "DELETE FROM groups WHERE id = ?", (group_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def create_group_invite(group_id: int, user_id: str, token: str, expires_at: str, role: str = "guest") -> bool:
    """オーナーまたは管理者メンバーが招待トークンを発行する。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT owner_user_id FROM groups WHERE id = ?", (group_id,))
        row = cur.fetchone()
        if not row:
            return False
        is_owner = row[0] == user_id
        if not is_owner:
            admin_cur = _execute(conn,
                "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ? AND role = 'admin'",
                (group_id, user_id))
            if not admin_cur.fetchone():
                return False
        _execute(
            conn,
            "INSERT OR IGNORE INTO group_invites (group_id, token, expires_at, role) VALUES (?, ?, ?, ?)",
            (group_id, token, expires_at, role),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def add_group_shared_list(group_id: int, user_id: str, collection_name: str):
    conn = _get_conn()
    try:
        _execute(
            conn,
            "INSERT OR IGNORE INTO group_shared_lists (group_id, owner_user_id, collection_name)"
            " VALUES (?, ?, ?)",
            (group_id, user_id, collection_name),
        )
        conn.commit()
    finally:
        conn.close()


def remove_group_shared_list(list_id: int, user_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "DELETE FROM group_shared_lists WHERE id = ? AND owner_user_id = ?",
            (list_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_user_collections(user_id: str) -> list:
    """ユーザーの都道府県別コレクション一覧を返す。"""
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            """SELECT l.prefecture, COUNT(*) as cnt
               FROM locations l
               JOIN saved_posts p ON l.post_id = p.id
               WHERE p.user_id = ? AND l.is_geocoded = 1 AND l.prefecture IS NOT NULL
               GROUP BY l.prefecture""",
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"name": r[0], "label": r[0], "count": r[1]} for r in rows]


def get_invite_info(token: str):
    """招待トークンのグループ情報を返す（認証不要）。有効期限切れ・存在しない場合は None。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, """
            SELECT gi.group_id, gi.expires_at, g.name,
                   (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS member_count,
                   gi.role
            FROM group_invites gi
            JOIN groups g ON gi.group_id = g.id
            WHERE gi.token = ?
        """, (token,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "group_id":     row[0],
        "expires_at":   row[1],
        "group_name":   row[2],
        "member_count": row[3],
        "role":         row[4] or "guest",
    }


def redeem_invite(token: str, user_id: str):
    """招待トークンを検証してグループに参加させる。"""
    from datetime import datetime
    conn = _get_conn()
    try:
        cur = _execute(
            conn,
            "SELECT group_id, expires_at, role FROM group_invites WHERE token = ?",
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return None
        if row[1] < datetime.now().isoformat():
            return None
        group_id = row[0]
        role     = row[2] or "guest"
        # メンバー追加（重複は無視）
        _execute(
            conn,
            "INSERT OR IGNORE INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
            (group_id, user_id, role),
        )
        cur = _execute(conn, "SELECT id, name FROM groups WHERE id = ?", (group_id,))
        g = cur.fetchone()
        conn.commit()
        return {"id": g[0], "name": g[1]} if g else None
    finally:
        conn.close()


# ── 許可メールアドレス管理 ─────────────────────────────────────────────────────

def get_allowed_emails() -> list:
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT email, added_by, added_at FROM allowed_emails ORDER BY added_at")
        return [{"email": r[0], "added_by": r[1], "added_at": r[2]} for r in cur.fetchall()]
    finally:
        conn.close()


def is_email_allowed(email: str) -> bool:
    """テーブルが空なら制限なし（全員許可）。空でなければ登録済みのみ許可。"""
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT COUNT(*) FROM allowed_emails")
        if cur.fetchone()[0] == 0:
            return True
        cur = _execute(conn, "SELECT 1 FROM allowed_emails WHERE email = ?", (email.lower(),))
        return cur.fetchone() is not None
    finally:
        conn.close()


def add_allowed_email(email: str, added_by: str) -> bool:
    conn = _get_conn()
    try:
        _execute(conn, "INSERT OR IGNORE INTO allowed_emails (email, added_by) VALUES (?, ?)",
                 (email.strip().lower(), added_by))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def remove_allowed_email(email: str) -> bool:
    conn = _get_conn()
    try:
        cur = _execute(conn, "DELETE FROM allowed_emails WHERE email = ?", (email.lower(),))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()
