"""
初回ログインセットアップスクリプト。

instagrapi がスマートフォン用モバイル API を経由してログインします。
スマートフォンの Instagram アプリと同じ API を使うため、
Web ブラウザのログインとは独立した認証セッションが作成されます。

2段階認証（メール・SMS コード）にも対応しています。
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SESSION_PATH = Path(__file__).parent / "browser_state" / "session.json"
SESSION_PATH.parent.mkdir(exist_ok=True)

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

print("=" * 50)
print("Instagram ログインセットアップ（モバイルAPI）")
print("=" * 50)

if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
    print("\nエラー: .env に INSTAGRAM_USERNAME と INSTAGRAM_PASSWORD を設定してください。")
    sys.exit(1)

print(f"\nアカウント: {INSTAGRAM_USERNAME}")

# 古いセッションを削除
if SESSION_PATH.exists():
    SESSION_PATH.unlink()
    print("古いセッションを削除しました。")

from instagrapi import Client
from instagrapi.exceptions import BadPassword, LoginRequired, TwoFactorRequired

cl = Client()

try:
    print("\nログイン中...")
    cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    print("ログイン成功！")

except TwoFactorRequired:
    print("\n2段階認証が必要です。")
    print("Instagram に登録したメールアドレスまたは電話番号に届いた認証コードを入力してください。")
    code = input("認証コード（6桁）: ").strip()
    try:
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, verification_code=code)
        print("2段階認証完了！")
    except Exception as e:
        print(f"\nエラー: {e}")
        sys.exit(1)

except BadPassword:
    print("\nエラー: パスワードが正しくありません。.env の INSTAGRAM_PASSWORD を確認してください。")
    sys.exit(1)

except LoginRequired as e:
    print(f"\nエラー: ログインに失敗しました。\n{e}")
    sys.exit(1)

except Exception as e:
    print(f"\nエラー: {e}")
    sys.exit(1)

cl.dump_settings(str(SESSION_PATH))
print(f"\nセッション保存完了: {SESSION_PATH}")

# 動作確認
try:
    user_info = cl.account_info()
    print(f"確認: @{user_info.username} としてログイン中")
except Exception:
    pass

print("""
セットアップ完了！

次回からは以下のコマンドで保存済み投稿を取得できます:
  python run_once.py       <- 1回だけ実行してテスト
  python batch/main.py     <- 1分ごとに定期実行

セッションは通常数週間〜数ヶ月有効です。
セッションが切れた場合のみ再度このスクリプトを実行してください。
""")
