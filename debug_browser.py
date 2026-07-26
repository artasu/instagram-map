"""ブラウザ診断スクリプト"""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
BASE = Path(__file__).parent
STATE = BASE / "browser_state" / "state.json"
USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

print(f"INSTAGRAM_USERNAME: {'設定済み' if USERNAME else '未設定!'}")
print(f"INSTAGRAM_PASSWORD: {'設定済み' if PASSWORD else '未設定!'}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context()
    page = context.new_page()

    print("\nInstagramのトップページへ移動中...")
    page.goto("https://www.instagram.com/", timeout=30000)
    page.wait_for_timeout(4000)

    url = page.url
    title = page.title()
    print(f"URL: {url}")
    print(f"Title: {title}")

    has_username_input = page.locator('input[name="username"]').count() > 0
    print(f"ログインフォームあり: {has_username_input}")

    page.screenshot(path=str(BASE / "debug_top.png"))
    print("スクリーンショット: debug_top.png")

    if has_username_input or "login" in url:
        print("\nログイン実行中...")
        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(6000)
        print(f"ログイン後URL: {page.url}")
        page.screenshot(path=str(BASE / "debug_after_login.png"))
        print("スクリーンショット: debug_after_login.png")

    # 保存済みページへ移動
    saved_url = f"https://www.instagram.com/{USERNAME}/saved/all-posts/"
    print(f"\n保存済みページへ移動: {saved_url}")
    page.goto(saved_url, timeout=30000)
    page.wait_for_timeout(4000)
    print(f"URL: {page.url}")
    page.screenshot(path=str(BASE / "debug_saved.png"))
    print("スクリーンショット: debug_saved.png")

    links = page.locator("a[href*='/p/']").all()
    print(f"検出した投稿リンク数: {len(links)}")
    for a in links[:5]:
        try:
            print(f"  {a.get_attribute('href')}")
        except Exception:
            pass

    # セッション保存
    STATE.parent.mkdir(exist_ok=True)
    context.storage_state(path=str(STATE))
    print(f"\nセッション保存: {STATE}")

    context.close()
    browser.close()

print("\n診断完了。debug_*.png を確認してください。")
