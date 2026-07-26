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
                    FOREIGN KEY (post_id) REFERENCES saved_posts(id)
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
        conn.commit()
    finally:
        conn.close()


def get_known_urls():
    conn = _get_conn()
    try:
        cur = _execute(conn, "SELECT instagram_url FROM saved_posts")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def insert_new_posts(posts):
    conn = _get_conn()
    try:
        _executemany(
            conn,
            "INSERT OR IGNORE INTO saved_posts"
            " (instagram_url, instagram_shortcode, caption, ig_saved_at)"
            " VALUES (?, ?, ?, ?)",
            [(p["instagram_url"], p.get("instagram_shortcode"),
              p.get("caption", ""), p.get("ig_saved_at")) for p in posts],
        )
        conn.commit()
    finally:
        conn.close()


def get_unprocessed_posts():
    conn = _get_conn()
    try:
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
    """1投稿から抽出した複数店舗を locations テーブルに登録する。"""
    conn = _get_conn()
    try:
        _executemany(
            conn,
            "INSERT INTO locations"
            " (post_id, shop_name, address, prefecture, city, genre, recommended_menus)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    post_id,
                    s.get("shop_name"),
                    s.get("address"),
                    s.get("prefecture"),
                    s.get("city"),
                    s.get("genre"),
                    json.dumps(s.get("recommended_menus") or [], ensure_ascii=False),
                )
                for s in shops
            ],
        )
        conn.commit()
    finally:
        conn.close()


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
