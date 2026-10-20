# -*- coding: utf-8 -*-
"""图书借阅管理系统 —— HTTP 入口（迭代一：只有注册登录）。

启动：python -m src.app  或  python start.py
"""
import json
import mimetypes
import os
import sys
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from src import config
from src.common import logger
from src.controller import auth_controller
from src.db.connection import ensure_ready
from src.service.auth_service import AuthError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
TEMPLATE_DIR = os.path.join(WEB_DIR, "templates")

PAGES = {
    "/login": "login.html",
    "/register": "register.html",
    "/home": "home.html",
}

MAX_BODY = 64 * 1024


class LibraryHandler(BaseHTTPRequestHandler):
    server_version = "LibrarySystem/1.0"

    # ---------- 基础工具 ----------
    def log_message(self, fmt, *args):
        logger.info("%s - %s" % (self.client_address[0], fmt % args))

    def _send(self, status, body, content_type="application/json; charset=utf-8", extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status, payload, extra_headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, data, "application/json; charset=utf-8", extra_headers)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise AuthError("请求体过大", 413)
        raw = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if "application/json" in ctype:
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                raise AuthError("请求数据不是合法的 JSON")
        # 表单提交也兼容一下，用浏览器直接调试时方便
        from urllib.parse import parse_qs
        params = parse_qs(raw.decode("utf-8"))
        return {k: v[0] for k, v in params.items()}

    def _cookie(self, name):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return None
        if name in cookie:
            return cookie[name].value
        return None

    def _session_cookie(self, token, max_age=None):
        parts = ["sid=%s" % token, "Path=/", "HttpOnly", "SameSite=Lax"]
        if max_age is not None:
            parts.append("Max-Age=%d" % max_age)
        return ("Set-Cookie", "; ".join(parts))

    # ---------- 路由 ----------
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        try:
            path = urlparse(self.path).path
            if path.startswith("/static/"):
                return self._serve_static(path[len("/static/"):])
            if path in PAGES and method == "GET":
                return self._serve_page(PAGES[path])
            if path == "/":
                return self._redirect("/home")

            if path == "/api/auth/me" and method == "GET":
                return self._handle_me()
            if path == "/api/auth/register" and method == "POST":
                return self._handle_register()
            if path == "/api/auth/login" and method == "POST":
                return self._handle_login()
            if path == "/api/auth/logout" and method == "POST":
                return self._handle_logout()

            if path.startswith("/api/"):
                return self._json(404, {"code": 404, "msg": "接口不存在", "data": None})
            return self._json(404, {"code": 404, "msg": "页面不存在", "data": None})
        except AuthError as e:
            self._json(e.code if e.code < 600 else 400,
                       {"code": e.code, "msg": e.message, "data": None})
        except Exception:
            # 调试时把堆栈打到控制台，正式环境只记日志
            traceback.print_exc()
            logger.warn("server error path=%s" % self.path)
            self._json(500, {"code": 500, "msg": "服务器内部错误", "data": None})

    def _serve_page(self, filename):
        full = os.path.join(TEMPLATE_DIR, filename)
        if not os.path.isfile(full):
            return self._json(404, {"code": 404, "msg": "页面不存在", "data": None})
        with open(full, "rb") as f:
            body = f.read()
        self._send(200, body, "text/html; charset=utf-8")

    def _serve_static(self, rel):
        # 只允许访问 static 目录下的文件，防止 ../ 穿越
        if ".." in rel or rel.startswith("/"):
            return self._json(403, {"code": 403, "msg": "非法路径", "data": None})
        full = os.path.join(STATIC_DIR, rel)
        if not os.path.isfile(full):
            return self._json(404, {"code": 404, "msg": "资源不存在", "data": None})
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            body = f.read()
        self._send(200, body, ctype)

    # ---------- API ----------
    def _ip(self):
        return self.client_address[0]

    def _handle_register(self):
        payload = self._read_body()
        result = auth_controller.handle_register(payload, self._ip())
        self._json(200, result)

    def _handle_login(self):
        payload = self._read_body()
        result = auth_controller.handle_login(payload, self._ip())
        token = result["data"]["token"]
        cookie = self._session_cookie(token, config.SESSION_MINUTES * 60)
        self._json(200, result, [cookie])

    def _handle_logout(self):
        token = self._cookie("sid")
        result = auth_controller.handle_logout(token, self._ip())
        cookie = self._session_cookie("", 0)
        self._json(200, result, [cookie])

    def _handle_me(self):
        result = auth_controller.handle_me(self._cookie("sid"))
        status = 200 if result["code"] == 0 else 401
        self._json(status, result)


def make_server(port=8000, host="127.0.0.1"):
    ensure_ready()
    # threading=True 是线程版，默认的 HTTPServer 只能串行处理，联调时差点以为接口超时
    return ThreadingHTTPServer((host, port), LibraryHandler)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ensure_ready()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), LibraryHandler)
    logger.info("图书借阅管理系统已启动：http://127.0.0.1:%d" % port)
    print("服务已启动，浏览器打开 http://127.0.0.1:%d/login" % port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
