# Instagram 保存済み店舗 → Google Maps 自動ピン止めバッチ

Instagramの保存済み投稿を1分ごと監視し、新規投稿があったときだけ住所をAIで抽出してGoogle Mapsにピン止めします。新規投稿がない場合はAPIを呼び出しません（費用$0）。

---

## 必要なもの

- Python 3.11+
- 各種APIキー（下記参照）

---

## APIキー取得手順

### 1. Google Maps API キー

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス（Googleアカウントが必要）
2. 「新しいプロジェクト」を作成
3. 「APIとサービス」→「ライブラリ」を開く
4. **Maps JavaScript API** を検索して「有効にする」
5. **Geocoding API** を検索して「有効にする」
6. 「認証情報」→「認証情報を作成」→「APIキー」
7. 作成されたキーをコピー

> 月$200の無料クレジットあり（個人利用では無料の範囲内）。
> 「APIキーの制限」でlocalhost等に制限をかけることを推奨。

### 2. Anthropic (Claude) API キー

1. [console.anthropic.com](https://console.anthropic.com/) にアクセス
2. アカウント作成・ログイン
3. 「API Keys」→「Create Key」
4. 作成されたキーをコピー

> 料金: `claude-haiku-4-5` で新規投稿1件あたり約$0.0001（0.01円）。新規なしなら$0。

---

## セットアップ

```bash
# 1. 依存パッケージをインストール
pip install -r requirements.txt
playwright install chromium

# 2. 環境変数を設定
cp .env.example .env
# .env をテキストエディタで開き、各キーを入力

# 3. map.html のAPIキーを設定
#    frontend/map.html の以下の行を編集:
#    const MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY";
#    → 実際のAPIキーに置換
```

---

## 起動方法

### バッチ起動（1分ごとに自動実行）

```bash
cd instagram-map
python batch/main.py
```

**初回起動時の注意**:
- Chromeが自動で起動し、Instagramのログインページが表示されます
- ユーザー名とパスワードは `.env` から自動入力されますが、2段階認証がある場合は手動で完了してください
- ログイン後、セッションが `browser_state/state.json` に保存されます（以降は自動ログイン）

### ログ確認

```
logs/batch.log  ← バッチ実行ログ（日時・新規件数・処理件数）
```

---

## 地図・リストを見る

バッチ起動後、別のターミナルで以下を実行:

```bash
cd instagram-map
python serve.py
```

> `serve.py` は `.env` から `GOOGLE_MAPS_API_KEY` を自動で読み込み、`map.html` に注入します。
> `python -m http.server` では API キーが注入されないため使わないでください。

ブラウザで:
- **地図**: http://localhost:8080/frontend/map.html
- **リスト**: http://localhost:8080/frontend/list.html

---

## ディレクトリ構成

```
instagram-map/
├── batch/
│   ├── main.py         # バッチ本体（1分ごとに自動実行）
│   ├── scraper.py      # Playwright: Instagramスクレイピング
│   ├── extractor.py    # Claude API: 住所抽出
│   ├── geocoder.py     # Google Geocoding: 座標変換
│   └── database.py     # SQLite: データ管理
├── frontend/
│   ├── map.html        # Google Maps表示
│   ├── list.html       # 都道府県・市区町村リスト
│   └── app.js          # 共通ロジック
├── data/
│   └── locations.json  # バッチが自動生成（地図表示用）
├── browser_state/
│   └── state.json      # Playwrightセッション（自動生成）
├── logs/
│   └── batch.log       # 実行ログ（自動生成）
├── instagram_map.db    # SQLiteデータベース（自動生成）
├── .env                # APIキー設定（要作成）
└── .env.example        # 設定テンプレート
```

---

## 動作の流れ

```
[1分ごと]
  ↓
  Instagram保存済み投稿URLを収集（Playwright）
  ↓
  DB照合 → 新規投稿がなければ終了（API費用: $0）
  ↓ 新規あり
  各投稿ページを開いてキャプション取得（Playwright）
  ↓
  Claude API で店名・住所・都道府県・市区町村を一括抽出
  ↓
  Google Geocoding で座標変換
  ↓
  DB保存 + locations.json 更新
```

---

## 注意事項

- PlaywrightによるInstagramスクレイピングはInstagram利用規約に抵触する可能性があります。個人利用・自己責任での使用としてください。
- Instagramのアカウントがブロックされるリスクを避けるため、バッチ間隔を短くしすぎないことを推奨します（1分以上を推奨）。
=======
# instagram-map
インスタで保存済みの投稿をGoogleMapに表示
