"""ログインページの状態を詳細診断するスクリプト"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
BASE = Path(__file__).parent
USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
HANDLE   = os.getenv("INSTAGRAM_HANDLE", "")

print(f"USERNAME: {USERNAME}")
print(f"HANDLE  : {HANDLE}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context()
    page = context.new_page()

    saved_url = f"https://www.instagram.com/{HANDLE}/saved/all-posts/"
    print(f"\n移動先: {saved_url}")
    page.goto(saved_url, timeout=30000)
    page.wait_for_timeout(5000)

    print(f"リダイレクト後URL: {page.url}")
    page.screenshot(path=str(BASE / "debug_login_01.png"))
    print("スクリーンショット: debug_login_01.png")

    # ページ内のすべての input を調べる
    inputs = page.locator("input").all()
    print(f"\nページ内の input 要素数: {len(inputs)}")
    for inp in inputs:
        try:
            name = inp.get_attribute("name") or ""
            typ  = inp.get_attribute("type") or ""
            placeholder = inp.get_attribute("placeholder") or ""
            print(f"  input name={name!r} type={typ!r} placeholder={placeholder!r}")
        except Exception:
            pass

    # ボタンも確認
    buttons = page.locator("button").all()
    print(f"\nページ内の button 要素数: {len(buttons)}")
    for btn in buttons[:5]:
        try:
            print(f"  button: {btn.inner_text()[:40]!r}")
        except Exception:
            pass

    # Cookie同意バナーなどを探す
    for selector in ["[data-testid='cookie-policy-dialog-accept-button']",
                     "button:has-text('Allow')", "button:has-text('許可')",
                     "button:has-text('Accept')", "button:has-text('承認')"]:
        if page.locator(selector).count() > 0:
            print(f"\nCookieバナーを発見: {selector} → クリックします")
            page.locator(selector).first.click()
            page.wait_for_timeout(2000)
            break

    page.screenshot(path=str(BASE / "debug_login_02.png"))
    print("\nスクリーンショット: debug_login_02.png（Cookie処理後）")

    # もう一度inputを確認
    inputs2 = page.locator("input").all()
    print(f"Cookie処理後の input 要素数: {len(inputs2)}")
    for inp in inputs2:
        try:
            name = inp.get_attribute("name") or ""
            print(f"  input name={name!r}")
        except Exception:
            pass

    browser.close()

print("\n診断完了。debug_login_01.png / debug_login_02.png を確認してください。")
