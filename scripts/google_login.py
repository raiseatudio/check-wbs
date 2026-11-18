"""Đăng nhập Google một lần và in refresh token. Không ghi token vào repo."""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from check_wbs import SHEETS_SCOPE, TOKEN_URL

REDIRECT_URI = "http://127.0.0.1:8765/"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765
WAIT_SECONDS = 180


def main() -> int:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print(
            "Cần GOOGLE_OAUTH_CLIENT_ID và GOOGLE_OAUTH_CLIENT_SECRET trong môi trường. "
            "Không ghi hai giá trị này vào repo.",
            file=sys.stderr,
        )
        return 1

    state = secrets.token_urlsafe(16)
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SHEETS_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    print("Mở URL này trên trình duyệt và đăng nhập tài khoản Google sẽ đọc Sheet:")
    print(auth_url)
    webbrowser.open(auth_url)
    try:
        code = wait_for_code(state)
        refresh_token = exchange_code(client_id, client_secret, code)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Đặt giá trị sau vào secret GOOGLE_OAUTH_REFRESH_TOKEN. Không commit token này.")
    print(refresh_token)
    return 0


def wait_for_code(expected_state: str) -> str:
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path not in {"", "/"}:
                self.reply(404, "Không có trang này.")
                return
            if query.get("state", [""])[0] != expected_state:
                result["error"] = "Sai state. Đóng trang và chạy lại script."
                self.reply(400, result["error"])
                return
            if query.get("error"):
                result["error"] = f"Google từ chối đăng nhập: {query['error'][0]}"
                self.reply(400, "Google từ chối đăng nhập. Quay lại terminal.")
                return
            code = query.get("code", [""])[0]
            if not code:
                self.reply(400, "Thiếu mã đăng nhập.")
                return
            result["code"] = code
            self.reply(200, "Đăng nhập xong. Quay lại terminal. Có thể đóng trang này.")

        def reply(self, status: int, text: str) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:
            return

    try:
        server = HTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    except OSError as exc:
        raise RuntimeError(f"Không mở được cổng {LISTEN_PORT}: {exc}") from exc
    server.timeout = 5
    deadline = time.time() + WAIT_SECONDS
    try:
        while "code" not in result and "error" not in result and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if result.get("error"):
        raise RuntimeError(result["error"])
    if "code" not in result:
        raise RuntimeError("Không nhận được mã đăng nhập. Chạy lại và chấp nhận quyền trong 3 phút.")
    return result["code"]


def exchange_code(client_id: str, client_secret: str, code: str) -> str:
    form = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL,
        data=form,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "check-wbs",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Đổi mã đăng nhập thất bại: HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Không kết nối được Google để đổi mã đăng nhập ({exc.reason}).") from None
    refresh_token = payload.get("refresh_token") if isinstance(payload, dict) else None
    if not isinstance(refresh_token, str) or not refresh_token:
        raise RuntimeError(
            "Google không trả refresh token. Vào tài khoản Google, gỡ quyền của app này, rồi chạy lại script."
        )
    return refresh_token


if __name__ == "__main__":
    sys.exit(main())
