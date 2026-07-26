"""
SQLite → PostgreSQL 一括移行スクリプト

使い方:
  DATABASE_URL=postgresql://... python migrate_sqlite_to_pg.py

実行すると以下のテーブルを順番に移行します:
  users, saved_posts, locations, genres, visits,
  visit_images (ファイル→BYTEA), user_groups, group_members,
  invite_links, shared_lists

注意:
  - 実行前に Render の PostgreSQL に init_db() を済ませておくこと
    (server.py を一度起動すると自動的に実行されます)
  - visit_images はローカルの data/visit_images/ から画像を読み込みます
  - 既存データがある場合は ON CONFLICT DO NOTHING でスキップします
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL 環境変数を設定してください")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
SQLITE_PATH = BASE_DIR / "instagram_map.db"
VISIT_IMAGES_DIR = BASE_DIR / "data" / "visit_images"

if not SQLITE_PATH.exists():
    print(f"ERROR: SQLite DB が見つかりません: {SQLITE_PATH}")
    sys.exit(1)

sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
pg_conn = psycopg2.connect(DATABASE_URL)
pg_cur = pg_conn.cursor()


def create_schema():
    """移行先 PostgreSQL にテーブルを作成する（既存テーブルはスキップ）。"""
    ddls = [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, google_id TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL, name TEXT, picture_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS user_groups (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, owner_id INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (owner_id) REFERENCES users(id))""",
        """CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            joined_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (group_id, user_id))""",
        """CREATE TABLE IF NOT EXISTS invite_links (
            token TEXT PRIMARY KEY, group_id INTEGER NOT NULL,
            created_by INTEGER NOT NULL, expires_at TEXT,
            used_count INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS shared_lists (
            id SERIAL PRIMARY KEY, group_id INTEGER NOT NULL,
            owner_user_id INTEGER NOT NULL, collection_name TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(group_id, owner_user_id, collection_name))""",
        """CREATE TABLE IF NOT EXISTS saved_posts (
            id SERIAL PRIMARY KEY, instagram_url TEXT UNIQUE NOT NULL,
            instagram_shortcode TEXT, caption TEXT, shop_name TEXT,
            address TEXT, prefecture TEXT, city TEXT, lat REAL, lng REAL,
            address_found INTEGER DEFAULT 0, is_geocoded INTEGER DEFAULT 0,
            ig_saved_at BIGINT, processed_at TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(), user_id INTEGER)""",
        """CREATE TABLE IF NOT EXISTS locations (
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL,
            shop_name TEXT, address TEXT, prefecture TEXT, city TEXT,
            lat REAL, lng REAL, is_geocoded INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(), user_id INTEGER,
            genre TEXT, recommended_menus TEXT, google_place_id TEXT,
            business_hours TEXT, google_rating REAL,
            google_ratings_total INTEGER, payment_methods TEXT,
            has_parking INTEGER, website_url TEXT,
            official_twitter_url TEXT, official_instagram_url TEXT,
            place_info_fetched INTEGER DEFAULT 0, place_info_fetched_at TEXT,
            FOREIGN KEY (post_id) REFERENCES saved_posts(id))""",
        """CREATE TABLE IF NOT EXISTS genres (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#757575', size REAL NOT NULL DEFAULT 1.0,
            keywords TEXT NOT NULL DEFAULT '[]', sort_order INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS visits (
            id SERIAL PRIMARY KEY, location_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, user_name TEXT,
            visited INTEGER DEFAULT 0, impression TEXT,
            rating INTEGER DEFAULT 0, want_again INTEGER DEFAULT 0,
            next_comment TEXT, visited_at TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS visit_images (
            id SERIAL PRIMARY KEY, visit_id INTEGER,
            location_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            filename TEXT NOT NULL, image_data BYTEA,
            created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS batch_log (
            id SERIAL PRIMARY KEY, run_at TIMESTAMPTZ DEFAULT NOW(),
            total_saved INTEGER, new_posts INTEGER,
            processed INTEGER, status TEXT, message TEXT)""",
    ]
    for ddl in ddls:
        pg_cur.execute(ddl)
    pg_conn.commit()
    print("スキーマ作成完了\n")


def migrate_table(name, rows, insert_sql, row_fn):
    count = 0
    for row in rows:
        params = row_fn(row)
        if params is None:
            continue
        try:
            pg_cur.execute("SAVEPOINT sp")
            pg_cur.execute(insert_sql, params)
            count += 1
        except Exception as e:
            pg_cur.execute("ROLLBACK TO SAVEPOINT sp")
            print(f"  skip ({e})")
    pg_conn.commit()
    print(f"  {name}: {count} 件移行")


print("=== SQLite → PostgreSQL 移行開始 ===\n")

print("テーブルを作成中...")
create_schema()

# ── users ──────────────────────────────────────────────────────────────────
print("users テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM users").fetchall()
migrate_table(
    "users", rows,
    """INSERT INTO users (id, google_id, email, name, picture_url, created_at)
       VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (google_id) DO NOTHING""",
    lambda r: (r["id"], r["google_id"], r["email"], r["name"],
               r["picture_url"], r["created_at"]),
)

# ── saved_posts ──────────────────────────────────────────────────────────
print("saved_posts テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM saved_posts").fetchall()
migrate_table(
    "saved_posts", rows,
    """INSERT INTO saved_posts
       (id, instagram_url, instagram_shortcode, caption, shop_name, address,
        prefecture, city, lat, lng, address_found, is_geocoded,
        ig_saved_at, processed_at, created_at, user_id)
       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
       ON CONFLICT (instagram_url) DO NOTHING""",
    lambda r: (r["id"], r["instagram_url"], r["instagram_shortcode"], r["caption"],
               r["shop_name"], r["address"], r["prefecture"], r["city"],
               r["lat"], r["lng"], r["address_found"], r["is_geocoded"],
               r["ig_saved_at"], r["processed_at"], r["created_at"],
               r["user_id"] if "user_id" in r.keys() else None),
)

# ── locations ────────────────────────────────────────────────────────────
print("locations テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM locations").fetchall()
cols = {r[1] for r in sqlite_conn.execute("PRAGMA table_info(locations)")}
migrate_table(
    "locations", rows,
    """INSERT INTO locations
       (id, post_id, shop_name, address, prefecture, city, lat, lng,
        is_geocoded, created_at, user_id, genre, recommended_menus,
        google_place_id, business_hours, google_rating, google_ratings_total,
        payment_methods, has_parking, website_url, official_twitter_url,
        official_instagram_url, place_info_fetched, place_info_fetched_at)
       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
       ON CONFLICT DO NOTHING""",
    lambda r: (
        r["id"], r["post_id"], r["shop_name"], r["address"], r["prefecture"],
        r["city"], r["lat"], r["lng"], r["is_geocoded"], r["created_at"],
        r["user_id"] if "user_id" in cols else None,
        r["genre"] if "genre" in cols else None,
        r["recommended_menus"] if "recommended_menus" in cols else None,
        r["google_place_id"] if "google_place_id" in cols else None,
        r["business_hours"] if "business_hours" in cols else None,
        r["google_rating"] if "google_rating" in cols else None,
        r["google_ratings_total"] if "google_ratings_total" in cols else None,
        r["payment_methods"] if "payment_methods" in cols else None,
        r["has_parking"] if "has_parking" in cols else None,
        r["website_url"] if "website_url" in cols else None,
        r["official_twitter_url"] if "official_twitter_url" in cols else None,
        r["official_instagram_url"] if "official_instagram_url" in cols else None,
        r["place_info_fetched"] if "place_info_fetched" in cols else 0,
        r["place_info_fetched_at"] if "place_info_fetched_at" in cols else None,
    ),
)

# ── genres ───────────────────────────────────────────────────────────────
print("genres テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM genres ORDER BY sort_order").fetchall()
migrate_table(
    "genres", rows,
    """INSERT INTO genres (id, name, icon, color, size, keywords, sort_order)
       VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING""",
    lambda r: (r["id"], r["name"], r["icon"], r["color"], r["size"],
               r["keywords"], r["sort_order"]),
)

# ── visits ───────────────────────────────────────────────────────────────
print("visits テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM visits").fetchall()
v_cols = {r[1] for r in sqlite_conn.execute("PRAGMA table_info(visits)")}
migrate_table(
    "visits", rows,
    """INSERT INTO visits
       (id, location_id, user_id, user_name, visited, impression, rating,
        want_again, next_comment, visited_at, updated_at)
       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
    lambda r: (
        r["id"], r["location_id"], r["user_id"],
        r["user_name"] if "user_name" in v_cols else None,
        r["visited"], r["impression"], r["rating"],
        r["want_again"], r["next_comment"], r["visited_at"], r["updated_at"],
    ),
)

# ── visit_images (ファイル → BYTEA) ───────────────────────────────────────
print("visit_images テーブルを移行中 (ファイル → BYTEA)...")
rows = sqlite_conn.execute("SELECT * FROM visit_images").fetchall()
vi_cols = {r[1] for r in sqlite_conn.execute("PRAGMA table_info(visit_images)")}
count = 0
for row in rows:
    filename = row["filename"]
    img_path = VISIT_IMAGES_DIR / filename
    if img_path.exists():
        image_data = psycopg2.Binary(img_path.read_bytes())
    else:
        print(f"  警告: ファイルが見つかりません: {filename} (NULL で登録)")
        image_data = None
    try:
        pg_cur.execute("SAVEPOINT sp")
        pg_cur.execute(
            """INSERT INTO visit_images
               (id, visit_id, location_id, user_id, filename, image_data, created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (
                row["id"],
                row["visit_id"] if "visit_id" in vi_cols else None,
                row["location_id"], row["user_id"], filename,
                image_data, row["created_at"],
            ),
        )
        count += 1
    except Exception as e:
        pg_cur.execute("ROLLBACK TO SAVEPOINT sp")
        print(f"  skip ({e})")
pg_conn.commit()
print(f"  visit_images: {count} 件移行")

# ── user_groups ───────────────────────────────────────────────────────────
print("user_groups テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM user_groups").fetchall()
migrate_table(
    "user_groups", rows,
    """INSERT INTO user_groups (id, name, owner_id, created_at)
       VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
    lambda r: (r["id"], r["name"], r["owner_id"], r["created_at"]),
)

# ── group_members ────────────────────────────────────────────────────────
print("group_members テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM group_members").fetchall()
migrate_table(
    "group_members", rows,
    """INSERT INTO group_members (group_id, user_id, joined_at)
       VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
    lambda r: (r["group_id"], r["user_id"], r["joined_at"]),
)

# ── invite_links ─────────────────────────────────────────────────────────
print("invite_links テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM invite_links").fetchall()
migrate_table(
    "invite_links", rows,
    """INSERT INTO invite_links (token, group_id, created_by, expires_at, used_count, created_at)
       VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (token) DO NOTHING""",
    lambda r: (r["token"], r["group_id"], r["created_by"],
               r["expires_at"], r["used_count"], r["created_at"]),
)

# ── shared_lists ─────────────────────────────────────────────────────────
print("shared_lists テーブルを移行中...")
rows = sqlite_conn.execute("SELECT * FROM shared_lists").fetchall()
migrate_table(
    "shared_lists", rows,
    """INSERT INTO shared_lists (id, group_id, owner_user_id, collection_name, created_at)
       VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
    lambda r: (r["id"], r["group_id"], r["owner_user_id"],
               r["collection_name"], r["created_at"]),
)

# ── SERIAL シーケンスをリセット ───────────────────────────────────────────
print("\nSERIAL シーケンスをリセット中...")
for table, col in [
    ("users", "id"), ("saved_posts", "id"), ("locations", "id"),
    ("visits", "id"), ("visit_images", "id"), ("user_groups", "id"),
    ("shared_lists", "id"),
]:
    pg_cur.execute(
        f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'),"
        f" COALESCE((SELECT MAX({col}) FROM {table}), 1))"
    )
pg_conn.commit()
print("シーケンスリセット完了")

sqlite_conn.close()
pg_conn.close()
print("\n=== 移行完了 ===")
