# -*- coding: utf-8 -*-
import unittest

from base import DbTestCase
from src.common import security


class SecurityTest(unittest.TestCase):
    def test_hash_not_plain(self):
        stored = security.make_password("abc12345")
        self.assertNotIn("abc12345", stored)
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))

    def test_verify_ok(self):
        stored = security.make_password("abc12345")
        self.assertTrue(security.check_password("abc12345", stored))

    def test_verify_wrong(self):
        stored = security.make_password("abc12345")
        self.assertFalse(security.check_password("abc12346", stored))

    def test_verify_broken_string(self):
        self.assertFalse(security.check_password("abc12345", "not-a-hash"))

    def test_same_pwd_diff_salt(self):
        a = security.make_password("abc12345")
        b = security.make_password("abc12345")
        self.assertNotEqual(a, b)

    def test_strength(self):
        self.assertTrue(security.password_strength_ok("abc12345")[0])
        self.assertFalse(security.password_strength_ok("12345678")[0])
        self.assertFalse(security.password_strength_ok("abcdefgh")[0])
        self.assertFalse(security.password_strength_ok("abc1234")[0])
        self.assertFalse(security.password_strength_ok("abc 12345")[0])

    def test_token_unique(self):
        self.assertNotEqual(security.new_token(), security.new_token())
        self.assertTrue(len(security.new_token()) >= 40)


class ValidatorTest(unittest.TestCase):
    def test_username(self):
        from src.common import validators
        self.assertTrue(validators.check_username("reader_01")[0])
        self.assertFalse(validators.check_username("a")[0])
        self.assertFalse(validators.check_username("中文名")[0])

    def test_phone(self):
        from src.common import validators
        self.assertTrue(validators.check_phone("")[0])
        self.assertTrue(validators.check_phone("13800138000")[0])
        self.assertFalse(validators.check_phone("1380013800")[0])


if __name__ == "__main__":
    unittest.main()
