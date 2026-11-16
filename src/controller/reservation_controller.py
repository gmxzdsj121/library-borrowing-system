# -*- coding: utf-8 -*-
"""预约接口控制器。"""
from src.service import reservation_service


def handle_reserve(payload, user):
    days = int(payload.get("borrowDays", 30))
    data = reservation_service.reserve_book(user["userId"], int(payload["bookId"]), days)
    return {"code": 0, "msg": "预约申请已提交，等待馆员审批", "data": data}


def handle_cancel(payload, user):
    data = reservation_service.cancel_reservation(
        user["userId"], int(payload["reservationId"]))
    return {"code": 0, "msg": "已取消预约", "data": data}


def handle_my_reservations(user):
    data = reservation_service.list_my_reservations(user["userId"])
    return {"code": 0, "msg": "ok", "data": data}


def handle_book_queue(query):
    data = reservation_service.list_reservations_by_book(int(query["bookId"]))
    return {"code": 0, "msg": "ok", "data": data}


def handle_pending():
    data = reservation_service.list_pending()
    return {"code": 0, "msg": "ok", "data": data}


def handle_approve(payload, user):
    data = reservation_service.approve(int(payload["reservationId"]), user["userId"])
    return {"code": 0, "msg": "审批通过", "data": data}


def handle_reject(payload, user):
    data = reservation_service.reject(
        int(payload["reservationId"]), payload.get("reason", ""), user["userId"])
    return {"code": 0, "msg": "已拒绝", "data": data}
