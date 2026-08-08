# Release Notes

---

## v2.0.0 — 2026-08-09

### 管理者画面・アクセス制限 DB 管理

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `batch/database.py` | `allowed_emails` テーブルを追加（PG / SQLite 両対応）。`ALLOWED_EMAILS` 環境変数からの初回シード処理を追加。`get_allowed_emails()` / `is_email_allowed()` / `add_allowed_email()` / `remove_allowed_email()` を新規追加。 |
| `app.py` | `ALLOWED_EMAILS` 環境変数による静的セットを廃止し、DB ベースのチェックに変更。`SUPER_USER_EMAILS` 定数（ハードコード2名）を追加。`_is_super_user()` / `_require_super_user()` ヘルパーを追加。`auth_me()` レスポンスに `is_super_user` フラグを追加。`GET/POST /api/admin/allowed-emails` および `DELETE /api/admin/allowed-emails/<email>` エンドポイントを追加。`/admin` ルートを追加（スーパーユーザーのみアクセス可）。 |
| `frontend/app.js` | `checkAuth()` にスーパーユーザー判定を追加。`is_super_user = true` の場合、ヘッダーナビに「管理者画面」リンクを動的注入。 |
| `frontend/admin.html` | 管理者画面を新規作成。許可メールアドレスの一覧表示・追加・削除 UI を実装。リスト空時の「全員許可」注記、スーパーユーザー説明文を表示。 |
| `document/TABLE_MODEL.md` | `allowed_emails` テーブル定義を追加。 |

#### 機能仕様

| 操作 | 動作 |
|---|---|
| スーパーユーザーでログイン | ヘッダーに「管理者画面」リンクが表示される |
| 一般ユーザーでログイン | 「管理者画面」リンクは表示されない |
| `/admin` に直接アクセス（非スーパーユーザー） | 403 エラー |
| 許可リストが空 | 全員がログイン可能 |
| 許可リストに1件以上登録 | 登録済みアドレスのみログイン可能 |
| スーパーユーザー | 常にログイン可能（リストを参照しない） |
| `ALLOWED_EMAILS` 環境変数 | 初回起動時のみ DB へシード（以降は DB で管理） |

---

## v1.9.0 — 2026-08-09

### ドキュメント追加

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `document/TABLE_MODEL.md` | テーブル定義書を新規作成。全10テーブルのカラム定義・型・制約・外部キー・ER図を記載。 |

---

## v1.8.0 — 2026-08-09

### ブラウザ翻訳対応（個人/グループ トグル）

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `frontend/app.js` | トグルボタン（個人/グループ）の active 状態判定をボタンのテキスト比較から `data-mode` 属性比較に変更。ブラウザ自動翻訳でテキストが変わっても白塗りハイライトが正しく機能するよう修正。 |

---

## v1.7.0 — 2026-08-09

### グループ機能バグ修正

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `batch/database.py` | `get_locations_for_group` から `AND p.user_id != ?` を削除。自分が `group_shared_lists` に登録した店舗もグループビューに表示されるよう修正。 |
| `frontend/app.js` | `loadLocations()` でグループ未選択時に `return []` → `throw new Error("グループが選択されていません。")` に変更。MAP・店舗一覧ページで空配列ではなくエラーメッセージが表示されるよう統一。 |
| `frontend/map.html` | エラーオーバーレイ表示中もヘッダーが操作可能になるよう `#top-header` の z-index を 20 → 110 に変更。エラー表示から `<h2>エラー</h2>` を削除し「グループが選択されていません。」のみ表示。 |
| `frontend/list.html` | `loadData()` エラー catch ブロックで `empty-msg` 要素が DOM に存在しない場合に NullError が発生するバグを修正（`main-content.innerHTML` を丸ごと書き換える形に変更）。`reloadListData()` でスピナー表示前に旧コンテンツをクリアするよう変更。プルダウン変更時のリロードが正しく機能するよう対応。 |

#### 修正前後の動作

| 操作 | 修正前 | 修正後 |
|---|---|---|
| グループトグル選択 → プルダウンをデフォルトに戻す | 「該当するお店が見つかりません」 or 旧データが残る | 「グループが選択されていません。」を表示 |
| 別グループへ切り替え | 旧グループのデータが残ることがあった | スピナー後に新グループのデータに切り替わる |
| 自分が共有登録した店舗をグループビューで表示 | 表示されなかった（自ユーザー除外条件により） | 正しく表示される |
| MAP エラー時にヘッダーをクリック | オーバーレイに隠れて操作不可 | ヘッダーは常に操作可能 |

---

## v1.6.0 — 2026-08-09

### Railway デプロイ対応

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `Procfile` | モジュール名を `server:app` → `app:app` に修正。`--workers 1 --timeout 120` を追加（Instagram バッチのタイムアウト対策）。 |
| `app.py` | `init_db()` をモジュールレベルで呼び出すよう変更（gunicorn 起動時に `__main__` ブロックが実行されないため）。`__main__` 内の重複呼び出しを削除。 |

---

## v1.5.0 — 2026-08-09

### UI 文言修正

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `frontend/map.html` `frontend/list.html` `frontend/groups.html` `frontend/top.html` `frontend/settings.html` | ヘッダーナビの「設定」を「カテゴリ設定」に変更。 |
| `frontend/groups.html` | グループ未作成時の案内文を「まだグループがありません。上のフォームからグループ名を入力し、「作成」ボタンを押下して作成してください。」に変更。 |

---

## v1.4.0 — 2026-08-09

### 個人/グループ切替トグルの追加

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `batch/database.py` | `get_locations_for_group(group_id, current_user_id)` を新規追加。グループの共有リスト登録ユーザーのロケーションを現在ユーザーの訪問情報付きで返す。 |
| `app.py` | `GET /api/groups/<id>/locations` エンドポイントを新規追加。グループメンバーのみアクセス可。 |
| `frontend/app.js` | ビューモード状態管理（`getViewMode`, `getViewGroupId` など）を追加。`loadLocations()` を更新し個人/グループに応じた API を呼び出すよう変更。`initViewToggle(callback)` / `_vtToggle` / `_vtGroupChange` を追加。 |
| `frontend/map.html` | ヘッダーに `#view-toggle-area` を追加。`initMap()` で `initViewToggle` を呼び出すよう変更。`reloadMapData()` を新規追加（フィルタ・マーカー再描画）。 |
| `frontend/list.html` | ヘッダーに `#view-toggle-area` を追加。`initViewToggle` 呼び出しを追加。`loadData()` のイベントリスナー二重登録防止を追加。`populatePrefFilter` / `populateGenreFilter` を再呼び出し時にリセットするよう修正。 |

#### 機能仕様

| 操作 | 動作 |
|---|---|
| 「個人」ボタンを押す | `GET /api/locations`（自分の保存済みデータ）を表示 |
| 「グループ」ボタンを押す | グループ選択プルダウンを表示 |
| グループを選択 | `GET /api/groups/<id>/locations`（グループ共有データ）を表示 |
| ページ遷移後 | localStorage に保存した選択状態が維持される |

---

## v1.3.0 — 2026-08-08

### グループ権限管理・退会機能の追加

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `batch/database.py` | `group_members` / `group_invites` に `role` カラム追加（migration）。`create_group_invite` に role 対応・管理者メンバーも招待可に変更。`redeem_invite` で招待時の role をメンバーに反映。`get_group_detail` でメンバー一覧に role を含める。`get_invite_info` に role を追加。`remove_group_member` / `leave_group` 関数を新規追加。 |
| `app.py` | `POST /api/groups/<id>/invite` に role パラメータ追加。`DELETE /api/groups/<id>/members/<user_id>`（管理者によるメンバー削除）を新規追加。`POST /api/groups/<id>/leave`（メンバーの自発的退会）を新規追加。 |
| `frontend/groups.html` | 招待フォームに権限セレクタ（管理者/ゲスト）を追加。メンバー一覧に role バッジ・管理者向け削除ボタンを追加。非オーナーに「グループから退会」ボタンを追加。招待セクションをオーナーのみ → 管理者全員に拡張。 |

#### 権限仕様

| 権限 | できること |
|---|---|
| オーナー | グループ削除・メンバー招待・メンバー削除 |
| 管理者 | メンバー招待（role 指定）・メンバー削除・グループから退会 |
| ゲスト | グループから退会のみ |

---

## v1.2.0 — 2026-08-08

### グループ招待をメール送信方式に変更・招待リンクバグ修正

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `batch/database.py` | `get_invite_info(token)` を新規追加（認証不要でグループ情報取得）。`get_user_name(user_id)` を新規追加。 |
| `app.py` | `GET /api/invite-info` エンドポイント追加。`POST /api/groups/<id>/invite` をメール送信方式に変更。`_send_invite_email` ヘルパー追加（Gmail SMTP）。招待メール文面に招待者名（DB取得）を表示。 |
| `frontend/groups.html` | 招待UIを「招待リンク生成」から「Gmailアドレス入力＋送信」に変更。 |
| `frontend/join.html` | トークンをURLクエリパラメータから正しく取得するよう修正（`location.pathname` → `URLSearchParams`）。API呼び出し先を `/api/invite-info` および `/api/join` に修正。 |
| `.env.example` | `GMAIL_USER` / `GMAIL_APP_PASSWORD` を追記。 |

---

## v1.1.0 — 2026-08-08

### 重複店舗の正規化

#### 変更内容

| ファイル | 変更概要 |
|---|---|
| `batch/database.py` | `_normalize_text()` ヘルパー追加（NFKC正規化＋ダッシュ統一）。`normalize_duplicate_locations()` を全角/半角差異を吸収した Python 側グルーピングに変更。`insert_locations()` を正規化済みセットによる重複チェックに変更。 |
| `app.py` | `POST /api/locations/normalize` エンドポイント追加。 |
| `batch/main.py` | `run_batch_for_user` に Step 6（重複店舗統合）を追加。 |

---

## v1.0.0 — 2026-08-08

### 初期リリース（マルチユーザー対応）

- Google OAuth ログイン
- Instagram 保存済み投稿の同期（instagrapi）
- Claude API による住所抽出
- Google Maps Geocoding
- 地図・一覧表示
- 訪問記録・レビュー機能
- グループ管理機能（基本）
- ジャンル設定機能
