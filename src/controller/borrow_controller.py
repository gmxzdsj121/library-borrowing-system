# -*- coding: utf-8 -*-
"""借阅 / 归还 / 续借 / 罚款 接口控制器。"""
from src.service import borrow_service


def handle_borrow(payload, user):
    # 馆员操作：readerId 是要借书的读者 user_id
    data = borrow_service.borrow_book(
        int(payload["readerId"]), payload["barcode"], user["userId"])
    return {"code": 0, "msg": "借书成功", "data": data}


def handle_return(payload, user):
    data = borrow_service.return_book(payload["barcode"], user["userId"])
    msg = "归还成功"
    if data["overdueDays"] > 0:
        msg += "，已生成 %.2f 元罚款" % data["fineAmount"]
    return {"code": 0, "msg": msg, "data": data}


def handle_renew(payload, user):
    data = borrow_service.renew_book(user["userId"], int(payload["recordId"]))
    return {"code": 0, "msg": "续借成功", "data": data}


def handle_my_borrows(user):
    data = borrow_service.list_my_borrows(user["userId"])
    return {"code": 0, "msg": "ok", "data": data}


def handle_fine_list(query, user):
    # 普通读者只看自己的；管理员/审核员可看全部，传 readerId=all
    status = query.get("status")
    if query.get("all") == "1" and user["role"] != "READER":
        data = borrow_service.list_fines(None, status)
    else:
        data = borrow_service.list_fines(user["userId"], status)
    return {"code": 0, "msg": "ok", "data": data}


def handle_fine_pay(payload, user):
    data = borrow_service.pay_fine(int(payload["fineId"]), user["userId"])
    return {"code": 0, "msg": "已缴纳", "data": data}


def handle_fine_waive(payload, user):
    # 审核统计管理员才能减免，角色校验在路由层做
    data = borrow_service.waive_fine(int(payload["fineId"]), user["userId"])
    return {"code": 0, "msg": "已减免", "data": data}
