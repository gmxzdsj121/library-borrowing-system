# -*- coding: utf-8 -*-
"""注册登录的业务测试。重点覆盖：重复注册、口令强度、失败锁定、冻结账号、会话失效。"""
import unittest

from base import DbTestCase
from src.dao import user_dao
from src.db.connection import get_conn
from src.service import auth_service
from src.service.auth_service import AuthError


class RegisterTest(DbTestCase):
    def test_register_ok(self):
        user = auth_service.register("reader88", "abc12345", "测试读者", "13800138000", ip="1.1.1.1")
        self.assertEqual(user["role"], "READER")
        self.assertEqual(user["status"], "ACTIVE")
        conn = get_conn()
        profile = conn.execute("SELECT * FROM reader_profile WHERE user_id = ?",
                               (user["userId"],)).fetchone()
        conn.close()
        self.assertIsNotNone(profile)
        self.assertEqual(profile["reader_no"], "reader88")

    def test_duplicate_username(self):
        auth_service.register("reader88", "abc12345", "测试读者")
        with self.assertRaises(AuthError) as ctx:
            auth_service.register("reader88", "abc12345", "另一个读者")
        self.assertIn("已被注册", ctx.exception.message)

    def test_weak_password(self):
        with self.assertRaises(AuthError):
            auth_service.register("reader88", "12345678", "测试读者")

    def test_bad_phone(self):
        with self.assertRaises(AuthError):
            auth_service.register("reader88", "abc12345", "测试读者", "1380013800")

    def test_bad_username(self):
        with self.assertRaises(AuthError):
            auth_service.register("a", "abc12345", "测试读者")

    def test_audit_written(self):
        user = auth_service.register("reader88", "abc12345", "测试读者")
        conn = get_conn()
        row = conn.execute("SELECT * FROM sys_audit_log WHERE action='REGISTER'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["user_id"], user["userId"])


class LoginTest(DbTestCase):
    def _make_user(self, username="reader88", password="abc12345", status="ACTIVE"):
        auth_service.register(username, "abc12345", "测试读者")
        if status != "ACTIVE":
            conn = get_conn()
            conn.execute("UPDATE sys_user SET status=? WHERE username=?", (status, username))
            conn.commit()
            conn.close()

    def test_login_ok(self):
        self._make_user()
        result = auth_service.login("reader88", "abc12345")
        self.assertEqual(result["user"]["username"], "reader88")
        self.assertGreaterEqual(len(result["token"]), 40)

    def test_login_wrong_pwd(self):
        self._make_user()
        with self.assertRaises(AuthError) as ctx:
            auth_service.login("reader88", "wrong1234")
        self.assertEqual(ctx.exception.code, 400)

    def test_login_unknown_user(self):
        with self.assertRaises(AuthError):
            auth_service.login("nobody", "abc12345")

    def test_five_fails_lock(self):
        self._make_user()
        for i in range(5):
            with self.assertRaises(AuthError):
                auth_service.login("reader88", "wrong1234")
        conn = get_conn()
        row = user_dao.find_user_by_name(conn, "reader88")
        conn.close()
        self.assertIsNotNone(row["lock_until"])
        with self.assertRaises(AuthError) as ctx:
            auth_service.login("reader88", "abc12345")
        self.assertEqual(ctx.exception.code, 429)

    def test_frozen_user(self):
        self._make_user(status="FROZEN")
        with self.assertRaises(AuthError) as ctx:
            auth_service.login("reader88", "abc12345")
        self.assertEqual(ctx.exception.code, 403)

    def test_success_resets_fail(self):
        self._make_user()
        for i in range(3):
            try:
                auth_service.login("reader88", "wrong1234")
            except AuthError:
                pass
        auth_service.login("reader88", "abc12345")
        conn = get_conn()
        row = user_dao.find_user_by_name(conn, "reader88")
        conn.close()
        self.assertEqual(row["fail_count"], 0)

    def test_session_lifecycle(self):
        self._make_user()
        result = auth_service.login("reader88", "abc12345")
        token = result["token"]
        me = auth_service.current_user(token)
        self.assertIsNotNone(me)
        auth_service.logout(token)
        self.assertIsNone(auth_service.current_user(token))

    def test_expired_session(self):
        self._make_user()
        result = auth_service.login("reader88", "abc12345")
        conn = get_conn()
        conn.execute("UPDATE sys_session SET expire_at='2020-01-01 00:00:00' WHERE token=?",
                     (result["token"],))
        conn.commit()
        conn.close()
        self.assertIsNone(auth_service.current_user(result["token"]))


if __name__ == "__main__":
    unittest.main()
