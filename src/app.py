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
from src.controller import (auth_controller, book_controller, borrow_controller,
                             reservation_controller, stats_controller, notice_controller)
from src.db.connection import ensure_ready, get_conn
from src.service import auth_service
from src.service.auth_service import AuthError

# 角色权限矩阵：接口前缀 -> 允许的角色；None 表示任意登录用户或匿名
ROLE_RULES = {
    "/api/book/search": None,
    "/api/book/detail": None,
    "/api/book/categories": None,
    "/api/book/create": ["LIBRARIAN", "AUDITOR"],
    "/api/book/list": ["LIBRARIAN", "AUDITOR"],
    "/api/book/add-copy": ["LIBRARIAN", "AUDITOR"],
    "/api/book/update": ["LIBRARIAN", "AUDITOR"],
    "/api/export/borrows": ["LIBRARIAN", "AUDITOR"],
    "/api/borrow/borrow": ["LIBRARIAN"],
    "/api/borrow/return": ["LIBRARIAN"],
    "/api/borrow/renew": ["READER"],
    "/api/borrow/my": ["READER"],
    "/api/fine/list": None,
    "/api/fine/pay": ["LIBRARIAN", "AUDITOR"],
    "/api/fine/waive": ["AUDITOR"],
    "/api/reserve/reserve": ["READER"],
    "/api/reserve/cancel": ["READER"],
    "/api/reserve/my": ["READER"],
    "/api/reserve/queue": None,
    # 迭代三：统计报表（FR-12）与通知公告（FR-13）
    "/api/stats/overview": ["LIBRARIAN", "AUDITOR"],
    "/api/stats/trend": ["LIBRARIAN", "AUDITOR"],
    "/api/stats/popular": ["LIBRARIAN", "AUDITOR"],
    "/api/stats/fine": ["LIBRARIAN", "AUDITOR"],
    "/api/notice/publish": ["LIBRARIAN", "AUDITOR"],
    "/api/notice/list": None,
    "/api/notice/read": None,
    "/api/notice/update": ["LIBRARIAN", "AUDITOR"],
    "/api/notice/delete": ["LIBRARIAN", "AUDITOR"],
    # 迭代三新增：个人信息、读者管理、借阅情况、预约审批
    "/api/auth/profile": None,
    "/api/auth/profile/update": None,
    "/api/auth/password": None,
    "/api/reader/list": ["LIBRARIAN", "AUDITOR"],
    "/api/reader/detail": ["LIBRARIAN", "AUDITOR"],
    "/api/reader/reset-password": ["LIBRARIAN", "AUDITOR"],
    "/api/borrow/active": ["LIBRARIAN", "AUDITOR"],
    "/api/reserve/pending": ["LIBRARIAN", "AUDITOR"],
    "/api/reserve/approve": ["LIBRARIAN"],
    "/api/reserve/reject": ["LIBRARIAN"],
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")
TEMPLATE_DIR = os.path.join(WEB_DIR, "templates")

PAGES = {
    "/login": "login.html",
    "/register": "register.html",
    "/home": "home.html",
    "/profile": "profile.html",
    "/books": "books.html",
    "/my": "my.html",
    "/admin/borrow": "admin_borrow.html",
    "/admin/return": "admin_return.html",
    "/admin/books": "admin_books.html",
    "/admin/fines": "admin_fines.html",
    "/admin/stats": "admin_stats.html",
    "/admin/notice": "admin_notice.html",
    "/admin/readers": "admin_readers.html",
    "/admin/borrows": "admin_borrows.html",
    "/admin/reservations": "admin_reservations.html",
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

            # ---- 迭代二：图书 / 借阅 / 预约 接口 ----
            if path == "/api/book/search" and method == "GET":
                return self._handle_book_search()
            if path == "/api/book/detail" and method == "GET":
                return self._handle_book_detail()
            if path == "/api/book/categories" and method == "GET":
                return self._json(200, book_controller.handle_categories())
            if path == "/api/book/create" and method == "POST":
                return self._handle_book_create()
            if path == "/api/book/list" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, book_controller.handle_list(user))
            if path == "/api/book/add-copy" and method == "POST":
                return self._handle_book_add_copy()
            if path == "/api/book/update" and method == "POST":
                return self._handle_book_update()
            if path == "/api/export/borrows" and method == "GET":
                return self._handle_export_borrows()

            if path == "/api/borrow/borrow" and method == "POST":
                return self._handle_borrow()
            if path == "/api/borrow/return" and method == "POST":
                return self._handle_return()
            if path == "/api/borrow/renew" and method == "POST":
                return self._handle_renew()
            if path == "/api/borrow/my" and method == "GET":
                return self._handle_my_borrows()
            if path == "/api/fine/list" and method == "GET":
                return self._handle_fine_list()
            if path == "/api/fine/pay" and method == "POST":
                return self._handle_fine_pay()
            if path == "/api/fine/waive" and method == "POST":
                return self._handle_fine_waive()

            if path == "/api/reserve/reserve" and method == "POST":
                return self._handle_reserve()
            if path == "/api/reserve/cancel" and method == "POST":
                return self._handle_reserve_cancel()
            if path == "/api/reserve/my" and method == "GET":
                return self._handle_my_reservations()
            if path == "/api/reserve/queue" and method == "GET":
                return self._json(200, reservation_controller.handle_book_queue(self._query()))

            # ---- 迭代三：统计报表 / 通知公告 接口 ----
            if path == "/api/stats/overview" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, stats_controller.handle_overview())
            if path == "/api/stats/trend" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, stats_controller.handle_trend(self._query()))
            if path == "/api/stats/popular" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, stats_controller.handle_popular(self._query()))
            if path == "/api/stats/fine" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, stats_controller.handle_fine_summary())

            if path == "/api/notice/publish" and method == "POST":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, notice_controller.handle_publish(self._read_body(), user))
            if path == "/api/notice/list" and method == "GET":
                user = self._require(None)
                return self._json(200, notice_controller.handle_list(user))
            if path == "/api/notice/read" and method == "POST":
                user = self._require(None)
                return self._json(200, notice_controller.handle_read(self._read_body(), user))
            if path == "/api/notice/update" and method == "POST":
                return self._handle_notice_update()
            if path == "/api/notice/delete" and method == "POST":
                return self._handle_notice_delete()

            # ---- 迭代三新增：个人信息 / 读者管理 / 借阅情况 / 预约审批 ----
            if path == "/api/auth/profile" and method == "GET":
                user = self._require(None)
                return self._json(200, auth_controller.handle_profile(user))
            if path == "/api/auth/profile/update" and method == "POST":
                user = self._require(None)
                return self._json(200, auth_controller.handle_update_profile(self._read_body(), user))
            if path == "/api/auth/password" and method == "POST":
                user = self._require(None)
                return self._json(200, auth_controller.handle_change_password(self._read_body(), user))

            if path == "/api/reader/list" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, self._handle_reader_list())
            if path == "/api/reader/detail" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, self._handle_reader_detail())
            if path == "/api/reader/reset-password" and method == "POST":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, auth_controller.handle_reset_reader_password(self._read_body(), user))

            if path == "/api/borrow/active" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, borrow_controller.handle_active_borrows())

            if path == "/api/reserve/pending" and method == "GET":
                user = self._require(["LIBRARIAN", "AUDITOR"])
                return self._json(200, reservation_controller.handle_pending())
            if path == "/api/reserve/approve" and method == "POST":
                user = self._require(["LIBRARIAN"])
                return self._json(200, reservation_controller.handle_approve(self._read_body(), user))
            if path == "/api/reserve/reject" and method == "POST":
                user = self._require(["LIBRARIAN"])
                return self._json(200, reservation_controller.handle_reject(self._read_body(), user))

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

    def _query(self):
        from urllib.parse import parse_qs
        raw = urlparse(self.path).query
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def _current_user(self):
        return auth_service.current_user(self._cookie("sid"))

    def _require(self, roles):
        """权限校验：roles=None 表示需要登录；列表表示必须是其中之一。"""
        user = self._current_user()
        if user is None:
            raise AuthError("请先登录", 401)
        if roles and user["role"] not in roles:
            raise AuthError("没有操作权限", 403)
        return user

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

    # ---- 图书 ----
    def _handle_book_search(self):
        user = self._current_user()  # 检索允许匿名
        result = book_controller.handle_search(self._query(), user)
        self._json(200, result)

    def _handle_book_detail(self):
        result = book_controller.handle_detail(self._query().get("bookId"))
        self._json(200, result)

    def _handle_book_create(self):
        user = self._require(["LIBRARIAN", "AUDITOR"])
        result = book_controller.handle_create(self._read_body(), user)
        self._json(200, result)

    def _handle_book_add_copy(self):
        user = self._require(["LIBRARIAN", "AUDITOR"])
        result = book_controller.handle_add_copy(self._read_body(), user)
        self._json(200, result)

    def _handle_book_update(self):
        user = self._require(["LIBRARIAN", "AUDITOR"])
        body = self._read_body()
        bid = self._query().get("bookId") or body.get("bookId")
        result = book_controller.handle_update(bid, body, user)
        self._json(200, result)

    def _handle_export_borrows(self):
        """导出所有借阅记录为 CSV 文件。"""
        self._require(["LIBRARIAN", "AUDITOR"])
        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT u.username, u.real_name, b.title, bc.barcode,
                          br.borrow_at, br.due_at, br.return_at, br.renew_count, br.status
                   FROM borrow_record br
                   JOIN reader_profile rp ON br.reader_id = rp.reader_id
                   JOIN sys_user u ON rp.user_id = u.user_id
                   JOIN book_copy bc ON br.copy_id = bc.copy_id
                   JOIN book b ON bc.book_id = b.book_id
                   ORDER BY br.borrow_at DESC"""
            ).fetchall()
        finally:
            conn.close()
        status_map = {"BORROWED": "借阅中", "OVERDUE": "已逾期", "RETURNED": "已归还"}
        lines = ["用户名,姓名,书名,条码,借出时间,应还时间,归还时间,续借次数,状态"]
        for r in rows:
            lines.append(",".join([
                r["username"], r["real_name"] or "", r["title"], r["barcode"],
                r["borrow_at"], r["due_at"], r["return_at"] or "",
                str(r["renew_count"]), status_map.get(r["status"], r["status"])
            ]))
        csv_body = "\ufeff" + "\n".join(lines)
        data = csv_body.encode("utf-8")
        self._send(200, data, "text/csv; charset=utf-8",
                   [("Content-Disposition", "attachment; filename=borrows.csv")])

    # ---- 借阅 / 归还 / 续借 ----
    def _handle_borrow(self):
        user = self._require(["LIBRARIAN"])
        result = borrow_controller.handle_borrow(self._read_body(), user)
        self._json(200, result)

    def _handle_return(self):
        user = self._require(["LIBRARIAN"])
        result = borrow_controller.handle_return(self._read_body(), user)
        self._json(200, result)

    def _handle_renew(self):
        user = self._require(["READER"])
        result = borrow_controller.handle_renew(self._read_body(), user)
        self._json(200, result)

    def _handle_my_borrows(self):
        user = self._require(["READER"])
        result = borrow_controller.handle_my_borrows(user, self._query())
        self._json(200, result)

    # ---- 罚款 ----
    def _handle_fine_list(self):
        user = self._require(None)
        result = borrow_controller.handle_fine_list(self._query(), user)
        self._json(200, result)

    def _handle_fine_pay(self):
        user = self._require(["LIBRARIAN", "AUDITOR"])
        result = borrow_controller.handle_fine_pay(self._read_body(), user)
        self._json(200, result)

    def _handle_fine_waive(self):
        user = self._require(["AUDITOR"])
        result = borrow_controller.handle_fine_waive(self._read_body(), user)
        self._json(200, result)

    # ---- 预约 ----
    def _handle_reserve(self):
        user = self._require(["READER"])
        result = reservation_controller.handle_reserve(self._read_body(), user)
        self._json(200, result)

    def _handle_reserve_cancel(self):
        user = self._require(["READER"])
        result = reservation_controller.handle_cancel(self._read_body(), user)
        self._json(200, result)

    def _handle_my_reservations(self):
        user = self._require(["READER"])
        result = reservation_controller.handle_my_reservations(user)
        self._json(200, result)

    # ---- 迭代三：读者管理 ----
    def _handle_reader_list(self):
        from src.dao import user_dao
        from src.db.connection import get_conn
        conn = get_conn()
        try:
            rows = conn.execute(
                """SELECT u.user_id, u.username, u.real_name, u.role, u.phone, u.status,
                          r.reader_no, r.reader_type, r.credit_score
                   FROM sys_user u
                   LEFT JOIN reader_profile r ON u.user_id = r.user_id
                   ORDER BY u.user_id"""
            ).fetchall()
            return {"code": 0, "msg": "ok", "data": [dict(r) for r in rows]}
        finally:
            conn.close()

    def _handle_reader_detail(self):
        from src.dao import user_dao, book_dao, borrow_dao
        from src.db.connection import get_conn
        user_id = self._query().get("userId")
        conn = get_conn()
        try:
            row = conn.execute(
                """SELECT u.user_id, u.username, u.real_name, u.role, u.phone, u.status,
                          u.created_at, r.reader_no, r.reader_type, r.credit_score, r.max_borrow
                   FROM sys_user u
                   LEFT JOIN reader_profile r ON u.user_id = r.user_id
                   WHERE u.user_id = ?""", (user_id,)
            ).fetchone()
            if not row:
                return {"code": 404, "msg": "读者不存在", "data": None}
            info = dict(row)
            rp = book_dao.get_reader_profile(conn, user_id)
            if rp:
                info["activeBorrows"] = borrow_dao.count_active_borrows(conn, rp["reader_id"])
                info["hasUnpaidFine"] = borrow_dao.has_unpaid_fine(conn, rp["reader_id"])
            return {"code": 0, "msg": "ok", "data": info}
        finally:
            conn.close()

    # ---- 迭代三：通知公告编辑 ----
    def _handle_notice_update(self):
        user = self._require(["LIBRARIAN", "AUDITOR"])
        payload = self._read_body()
        result = notice_controller.handle_update(payload, user)
        self._json(200, result)

    def _handle_notice_delete(self):
        user = self._require(["LIBRARIAN", "AUDITOR"])
        payload = self._read_body()
        result = notice_controller.handle_delete(payload, user)
        self._json(200, result)


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
