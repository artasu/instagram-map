"""保存済みページのスクリーンショットと投稿リンクを診断"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
BASE = Path(__file__).parent
STATE = BASE / "browser_state" / "state.json"
HANDLE = os.getenv("INSTAGRAM_HANDLE", "").strip()

print(f"HANDLE: {HANDLE}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    context = browser.new_context(storage_state=str(STATE))
    page = context.new_page()

    for try_url in [
        f"https://www.instagram.com/{HANDLE}/saved/all-posts/",
        f"https://www.instagram.com/{HANDLE}/saved/",
    ]:
        print(f"\n移動: {try_url}")
        page.goto(try_url, timeout=30000)
        page.wait_for_timeout(4000)
        print(f"現在のURL: {page.url}")

        if "saved" in page.url and "login" not in page.url:
            break

    page.screenshot(path=str(BASE / "debug_saved_page.png"), full_page=False)
    print("スクリーンショット: debug_saved_page.png")

    # /p/ リンクを探す
    links = page.locator("a[href*='/p/']").all()
    print(f"\n/p/ リンク数: {len(links)}")
    for a in links[:10]:
        try:
            print(f"  {a.get_attribute('href')}")
        except Exception:
            pass

    # /reel/ リンクも確認（動画保存の場合）
    reel_links = page.locator("a[href*='/reel/']").all()
    print(f"/reel/ リンク数: {len(reel_links)}")
    for a in reel_links[:5]:
        try:
            print(f"  {a.get_attribute('href')}")
        except Exception:
            pass

    # ページ内のすべての <a> を確認
    all_links = page.locator("a").all()
    print(f"\n全 <a> タグ数: {len(all_links)}")

    # ページのHTMLを一部保存
    html = page.content()
    (BASE / "debug_saved_page.html").write_text(html[:5000], encoding="utf-8")
    print("HTML冒頭5000文字: debug_saved_page.html")

    context.close()
    browser.close()

print("\n診断完了")
