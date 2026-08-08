# テーブル定義書

**対象DB**: SQLite（ローカル開発）/ PostgreSQL（Railway 本番）  
**定義ファイル**: `batch/database.py` — `init_db()`

---

## 一覧

| テーブル名 | 概要 |
|---|---|
| `saved_posts` | Instagram 保存済み投稿 |
| `locations` | 店舗情報（住所・緯度経度） |
| `users` | ログインユーザー |
| `visits` | 訪問記録 |
| `visit_images` | 訪問記録の画像 |
| `groups` | グループ |
| `group_members` | グループメンバー |
| `group_invites` | グループ招待トークン |
| `group_shared_lists` | グループへの共有リスト登録 |
| `batch_log` | バッチ実行ログ |

---

## saved_posts

Instagram の保存済み投稿を格納する。1投稿が複数店舗を含む場合は `locations` に分割される。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `instagram_url` | TEXT | ✅ | — | 投稿 URL（UNIQUE） |
| `instagram_shortcode` | TEXT | — | NULL | 投稿ショートコード |
| `caption` | TEXT | — | NULL | キャプション本文 |
| `shop_name` | TEXT | — | NULL | 店舗名（Claude 抽出） |
| `address` | TEXT | — | NULL | 住所（Claude 抽出） |
| `prefecture` | TEXT | — | NULL | 都道府県 |
| `city` | TEXT | — | NULL | 市区町村 |
| `lat` | REAL | — | NULL | 緯度 |
| `lng` | REAL | — | NULL | 経度 |
| `address_found` | INTEGER | — | 0 | 住所抽出状態（0=未処理 / 1=成功 / 2=失敗） |
| `is_geocoded` | INTEGER | — | 0 | ジオコーディング済みフラグ（0/1） |
| `ig_saved_at` | INTEGER / BIGINT | — | NULL | Instagram 保存日時（UNIX タイムスタンプ） |
| `processed_at` | TEXT | — | NULL | 処理日時（ISO 8601） |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | レコード作成日時 |
| `user_id` | TEXT | — | NULL | 所有ユーザー ID（FK: `users.id`） |

**インデックス / 制約**
- `instagram_url` UNIQUE

---

## locations

`saved_posts` から抽出した店舗情報。ジオコーディング済みのレコードのみ地図・一覧に表示される。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `post_id` | INTEGER | ✅ | — | FK: `saved_posts.id` |
| `shop_name` | TEXT | — | NULL | 店舗名 |
| `address` | TEXT | — | NULL | 住所 |
| `prefecture` | TEXT | — | NULL | 都道府県 |
| `city` | TEXT | — | NULL | 市区町村 |
| `lat` | REAL | — | NULL | 緯度 |
| `lng` | REAL | — | NULL | 経度 |
| `genre` | TEXT | — | NULL | ジャンル（カテゴリ設定で上書き可） |
| `recommended_menus` | TEXT | — | NULL | おすすめメニュー（JSON 配列） |
| `is_geocoded` | INTEGER | — | 0 | ジオコーディング済みフラグ（0/1） |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | レコード作成日時 |
| `google_rating` | REAL | — | NULL | Google 評価（例: 4.2） |
| `google_ratings_total` | INTEGER | — | NULL | Google 評価件数 |
| `business_hours` | TEXT | — | NULL | 営業時間（JSON 配列、曜日順） |
| `payment_methods` | TEXT | — | NULL | 対応支払方法（JSON 配列） |
| `has_parking` | INTEGER | — | NULL | 駐車場あり（0/1） |
| `website_url` | TEXT | — | NULL | 公式 Web サイト URL |
| `official_twitter_url` | TEXT | — | NULL | 公式 X（旧 Twitter）URL |
| `official_instagram_url` | TEXT | — | NULL | 公式 Instagram URL |
| `place_info_fetched` | INTEGER | — | 0 | Google Places 情報取得済みフラグ（0/1） |
| `place_info_fetched_at` | TEXT | — | NULL | Places 情報取得日時（ISO 8601） |

**外部キー**
- `post_id` → `saved_posts.id`

---

## users

Google OAuth でログインしたユーザー情報。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | TEXT | ✅ | — | 主キー（Google ユーザー ID） |
| `email` | TEXT | — | NULL | メールアドレス |
| `name` | TEXT | — | NULL | 表示名 |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | レコード作成日時 |

---

## visits

ユーザーによる店舗への訪問記録。1店舗に対して複数ユーザーが記録できる。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `loc_id` | INTEGER | ✅ | — | FK: `locations.id` |
| `user_id` | TEXT | ✅ | — | FK: `users.id` |
| `visited` | INTEGER | — | 1 | 訪問済みフラグ（0/1） |
| `rating` | INTEGER | — | 0 | 評価（0〜5） |
| `impression` | TEXT | — | NULL | 感想・メモ |
| `want_again` | INTEGER | — | 0 | また行きたいフラグ（0/1） |
| `next_comment` | TEXT | — | NULL | 次回メモ |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | 作成日時 |
| `updated_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | 更新日時 |

**外部キー**
- `loc_id` → `locations.id`
- `user_id` → `users.id`

---

## visit_images

訪問記録に添付された画像ファイル情報。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `visit_id` | INTEGER | ✅ | — | FK: `visits.id` |
| `filename` | TEXT | ✅ | — | 保存ファイル名 |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | アップロード日時 |

**外部キー**
- `visit_id` → `visits.id`

---

## groups

ユーザーが作成するグループ。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `name` | TEXT | ✅ | — | グループ名 |
| `owner_user_id` | TEXT | ✅ | — | オーナーユーザー ID（FK: `users.id`） |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | 作成日時 |

**外部キー**
- `owner_user_id` → `users.id`（論理参照）

---

## group_members

グループへの参加メンバー（オーナーを除く招待済みメンバー）。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `group_id` | INTEGER | ✅ | — | FK: `groups.id` |
| `user_id` | TEXT | ✅ | — | FK: `users.id` |
| `role` | TEXT | — | `'guest'` | 権限（`'admin'` / `'guest'`） |
| `joined_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | 参加日時 |

**外部キー**
- `group_id` → `groups.id`
- `user_id` → `users.id`

**権限仕様**

| role | できること |
|---|---|
| オーナー（`groups.owner_user_id`） | グループ削除・メンバー招待・メンバー削除 |
| `admin` | メンバー招待（role 指定）・メンバー削除・グループ退会 |
| `guest` | グループ退会のみ |

---

## group_invites

グループへの招待トークン。有効期限付き。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `group_id` | INTEGER | ✅ | — | FK: `groups.id` |
| `token` | TEXT | ✅ | — | 招待トークン（UNIQUE） |
| `expires_at` | TEXT | ✅ | — | 有効期限（ISO 8601） |
| `role` | TEXT | — | `'guest'` | 参加時に付与される role |
| `created_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | 発行日時 |

**外部キー**
- `group_id` → `groups.id`

---

## group_shared_lists

各ユーザーが自分の店舗コレクション（都道府県単位 or 全件）をグループに共有登録したレコード。グループ表示時はこのテーブルを JOIN して対象店舗を絞り込む。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `group_id` | INTEGER | ✅ | — | FK: `groups.id` |
| `owner_user_id` | TEXT | ✅ | — | 共有元ユーザー ID（FK: `users.id`） |
| `collection_name` | TEXT | ✅ | — | 共有範囲（`'__all__'` = 全件 / 都道府県名） |

**外部キー**
- `group_id` → `groups.id`

**備考**  
- `collection_name = '__all__'` の場合、そのユーザーの全ジオコーディング済み店舗が対象。  
- 都道府県名（例: `'東京都'`）の場合、その都道府県の店舗のみ対象。  
- グループビューの取得クエリ: `locations.prefecture = collection_name OR collection_name = '__all__'`

---

## batch_log

Instagram 保存済み投稿の同期バッチ実行結果ログ。

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---|---|---|---|---|
| `id` | INTEGER / SERIAL | ✅ | AUTO | 主キー |
| `run_at` | TEXT / TIMESTAMPTZ | — | CURRENT_TIMESTAMP | 実行日時 |
| `total_saved` | INTEGER | — | NULL | 取得済み投稿総数 |
| `new_posts` | INTEGER | — | NULL | 今回新規取得数 |
| `processed` | INTEGER | — | NULL | 今回処理数（住所抽出） |
| `status` | TEXT | — | NULL | 実行結果（`'success'` / `'error'` 等） |
| `message` | TEXT | — | NULL | 詳細メッセージ |

---

## ER 図（概略）

```
users
  │
  ├─< saved_posts ──< locations ──< visits ──< visit_images
  │
  ├─< groups
  │     │
  │     ├─< group_members
  │     ├─< group_invites
  │     └─< group_shared_lists
  │
  └─ (visits.user_id)
```
