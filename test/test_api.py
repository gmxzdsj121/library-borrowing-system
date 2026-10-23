# -*- coding: utf-8 -*-
"""接口级冒烟测试：真的起一个 HTTP 服务，走一遍注册→登录→当前用户→退出。"""
import http.cookiejar
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config  # noqa: E402
from src import app as app_module  # noqa: E402
from src.db import connection  # noqa: E402


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        config.DB_PATH = cls.db_path
        connection.init_schema()

        cls.httpd = app_module.make_server(port=0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        try:
            os.remove(cls.db_path)
        except OSError:
            pass

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST")
        try:
            resp = self.opener.open(req)
            return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def _get(self, path):
        try:
            resp = self.opener.open(self.base + path)
            return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def test_01_login_page(self):
        status, body = self._get("/login")
        self.assertEqual(status, 200)
        self.assertIn("图书借阅管理系统", body)

    def test_02_register_and_login(self):
        code, data = self._post("/api/auth/register", {
            "username": "apitester01", "password": "abc12345",
            "realName": "接口测试", "phone": "13800138000"})
        self.assertEqual(code, 200)
        self.assertEqual(data["code"], 0)

        code, data = self._post("/api/auth/login", {
            "username": "apitester01", "password": "abc12345"})
        self.assertEqual(code, 200)
        self.assertEqual(data["code"], 0)
        self.assertEqual(data["data"]["user"]["role"], "READER")

        status, body = self._get("/api/auth/me")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["data"]["username"], "apitester01")

    def test_03_duplicate_register(self):
        code, data = self._post("/api/auth/register", {
            "username": "apitester01", "password": "abc12345", "realName": "重复注册"})
        self.assertEqual(code, 400)
        self.assertNotEqual(data["code"], 0)

    def test_04_weak_password(self):
        code, data = self._post("/api/auth/register", {
            "username": "apitester02", "password": "12345678", "realName": "弱口令"})
        self.assertEqual(code, 400)

    def test_05_me_without_login(self):
        opener = urllib.request.build_opener()
        try:
            resp = opener.open(self.base + "/api/auth/me")
            status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 401)

    def test_06_logout(self):
        self._post("/api/auth/login", {"username": "apitester01", "password": "abc12345"})
        code, data = self._post("/api/auth/logout", {})
        self.assertEqual(code, 200)
        code, _ = self._post("/api/auth/logout", {})
        self.assertEqual(code, 200)


if __name__ == "__main__":
    unittest.main()
