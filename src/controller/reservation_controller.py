# -*- coding: utf-8 -*-
"""预约接口控制器。"""
from src.service import reservation_service


def handle_reserve(payload, user):
    data = reservation_service.reserve_book(user["userId"], int(payload["bookId"]))
    return {"code": 0, "msg": "预约成功，排队号 %d" % data["queueNo"], "data": data}


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
