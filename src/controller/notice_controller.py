# -*- coding: utf-8 -*-
"""通知公告接口控制器（FR-13）。"""
from src.service import notice_service


def handle_publish(payload, user):
    data = notice_service.create_notice(
        payload["title"], payload.get("content", ""), user["userId"])
    return {"code": 0, "msg": "发布成功", "data": data}


def handle_list(user):
    return {"code": 0, "msg": "ok",
            "data": notice_service.list_notices(user["userId"])}


def handle_read(payload, user):
    notice_service.mark_read(int(payload["noticeId"]), user["userId"])
    return {"code": 0, "msg": "ok", "data": None}
