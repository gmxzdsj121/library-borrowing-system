# -*- coding: utf-8 -*-
"""口令散列与会话令牌。课程要求口令加密存储，这里用标准库 pbkdf2_hmac。"""
import base64
import hashlib
import hmac
import os
import re
import secrets

from src import config


def make_password(raw_password):
    """返回 pbkdf2_sha256$轮数$盐$散列 形式的字符串，数据库里不存明文。"""
    if not raw_password:
        raise ValueError("口令不能为空")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, config.PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        config.PBKDF2_ROUNDS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def check_password(raw_password, stored):
    """校验口令。用 compare_digest 防时序攻击。"""
    if not stored or not raw_password:
        return False
    try:
        algo, rounds, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expect = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(dk, expect)
    except (ValueError, TypeError):
        return False


def password_strength_ok(raw_password):
    """至少 8 位，且同时含字母和数字。返回 (是否合格, 提示语)"""
    if not raw_password or len(raw_password) < 8:
        return False, "口令至少 8 位"
    if not re.search(r"[A-Za-z]", raw_password):
        return False, "口令需包含字母"
    if not re.search(r"[0-9]", raw_password):
        return False, "口令需包含数字"
    if re.search(r"\s", raw_password):
        return False, "口令不能含空格"
    return True, ""


def new_token():
    return secrets.token_urlsafe(32)
