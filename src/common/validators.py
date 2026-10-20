# -*- coding: utf-8 -*-
"""入参校验，单独抽出来方便测试。"""
import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{4,20}$")
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def check_username(username):
    if not username:
        return False, "登录名不能为空"
    if not USERNAME_RE.match(username):
        return False, "登录名需为 4-20 位字母、数字或下划线"
    return True, ""


def check_real_name(name):
    if not name or not name.strip():
        return False, "姓名不能为空"
    if len(name.strip()) > 20:
        return False, "姓名过长"
    return True, ""


def check_phone(phone):
    """手机号可以为空（有些老年读者没登记），填了就必须合法"""
    if not phone:
        return True, ""
    if not PHONE_RE.match(phone):
        return False, "手机号格式不正确"
    return True, ""
