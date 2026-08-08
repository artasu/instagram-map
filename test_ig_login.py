"""
Instagram ログイン詳細診断スクリプト
usage: python test_ig_login.py
"""
import getpass, sys, json

username = input("Instagram ユーザー名（@なし、メールアドレス不可）: ").strip()
password = getpass.getpass("Instagram パスワード: ")

print("\n--- 診断開始 ---")
print(f"username: {username!r}")
print(f"password length: {len(password)}, has special chars: {any(c in password for c in '@#$%^&*!/')}")

try:
    from instagrapi import Client
except ImportError as e:
    print(f"[FATAL] {e}"); sys.exit(1)

cl = Client()

# Instagram の公開鍵を取得できるか確認
print("\n[1] Instagram サーバー公開鍵の取得...")
try:
    enc_key = cl.password_encrypt(password)
    print(f"    OK - 暗号化成功 (長さ: {len(enc_key)})")
except Exception as e:
    print(f"    FAIL - {type(e).__name__}: {e}")
    print("    → Instagram の公開鍵取得に失敗。ネットワーク/ファイアウォールを確認してください。")

# ログイン試行（last_json を確認）
print("\n[2] ログイン試行...")
try:
    result = cl.login(username, password)
    print(f"    OK - ログイン成功！ user_id={cl.user_id}")
except Exception as e:
    exc_name = type(e).__name__
    print(f"    FAIL - {exc_name}: {e}")

    # Instagram が返した生レスポンスを確認
    last = getattr(cl, "last_json", {})
    print(f"\n[3] Instagram の生レスポンス:")
    print(json.dumps(last, ensure_ascii=False, indent=2))

    # 原因判定
    print("\n[4] 原因判定:")
    error_type = last.get("error_type", "")
    message    = last.get("message", "")

    if "checkpoint" in str(last).lower() or "challenge" in str(last).lower():
        print("  → 実態は ChallengeRequired（セキュリティチャレンジ）です。")
        print("    Instagram が BadPassword を偽装して返しています。")
        print("    スマホで Instagram を開いて不審なログイン通知を承認してください。")
    elif error_type == "bad_password":
        print(f"  → Instagram が error_type=bad_password を返しています。")
        print("    考えられる原因：")
        print("    1. パスワードが間違っている（アプリで再確認）")
        print("    2. パスワードに特殊文字があり暗号化に失敗している")
        print("    3. メールアドレスで入力している（ユーザー名を使うこと）")
    elif "two_factor" in str(last).lower():
        print("  → 2段階認証（2FA）が必要です。")
    else:
        print(f"  → 不明なエラー。error_type={error_type!r}, message={message!r}")
