"""
ビューワー用HTTPサーバー。
map.html を配信するとき .env の GOOGLE_MAPS_API_KEY を自動注入します。
起動: python serve.py
"""
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

ROOT = Path(__file__).parent

MIME = {
    ".html": "text/html",
    ".js": "application/javascript",
    ".json": "application/json",
    ".css": "text/css",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path.lstrip("/") or "frontend/map.html"

        filepath = ROOT / path
        if not filepath.exists() or not filepath.is_file():
            self._respond(404, b"Not Found", "text/plain")
            return

        content = filepath.read_bytes()

        # map.html だけ API キーを注入
        if filepath.name == "map.html":
            api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
            content = content.replace(
                b"YOUR_GOOGLE_MAPS_API_KEY", api_key.encode()
            )

        mime = MIME.get(filepath.suffix, "application/octet-stream")
        self._respond(200, content, mime)

    def _respond(self, code, body, mime):
        self.send_response(code)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # ログ出力を抑制


if __name__ == "__main__":
    port = 8080
    server = HTTPServer(("localhost", port), Handler)
    print(f"サーバー起動: http://localhost:{port}/frontend/map.html")
    print(f"リスト:       http://localhost:{port}/frontend/list.html")
    print("停止するには Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("サーバー停止")
