# -*- coding: utf-8 -*-
"""认证接口的控制器：只负责收参数、调用 service、拼返回结构。"""
from src.service import auth_service


def handle_register(payload, ip):
    user = auth_service.register(
        username=payload.get("username"),
        password=payload.get("password"),
        real_name=payload.get("realName"),
        phone=payload.get("phone", ""),
        reader_type=payload.get("readerType", "STUDENT"),
        ip=ip,
    )
    return {"code": 0, "msg": "注册成功", "data": user}


def handle_login(payload, ip):
    result = auth_service.login(payload.get("username"), payload.get("password"), ip)
    return {"code": 0, "msg": "登录成功", "data": result}


def handle_logout(token, ip):
    auth_service.logout(token, ip)
    return {"code": 0, "msg": "已退出登录", "data": None}


def handle_me(token):
    user = auth_service.current_user(token)
    if user is None:
        return {"code": 401, "msg": "未登录或会话已过期", "data": None}
    return {"code": 0, "msg": "ok", "data": user}


def handle_profile(user):
    info = auth_service.get_profile(user["userId"])
    return {"code": 0, "msg": "ok", "data": info}


def handle_update_profile(payload, user):
    info = auth_service.update_profile(
        user["userId"],
        real_name=payload.get("realName"),
        phone=payload.get("phone"),
    )
    return {"code": 0, "msg": "信息已更新", "data": info}


def handle_change_password(payload, user):
    result = auth_service.change_password(
        user["userId"],
        old_password=payload.get("oldPassword"),
        new_password=payload.get("newPassword"),
        admin_key=payload.get("adminKey"),
    )
    return {"code": 0, "msg": "密码已修改", "data": result}
