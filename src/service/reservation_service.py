# -*- coding: utf-8 -*-
"""预约借书业务逻辑。迭代二新增。"""
from src.common import logger
from src.dao import book_dao, borrow_dao, reservation_dao, user_dao
from src.db.connection import get_conn
from src.service.auth_service import AuthError


def _reader_of(conn, user_id):
    rp = book_dao.get_reader_profile(conn, user_id)
    if not rp:
        raise AuthError("该账号没有读者档案", 403)
    return rp


def reserve_book(reader_user_id, book_id, borrow_days=30):
    """读者预约某本书（需要没有可借复本，且没有未完成的同书预约）。
    预约后状态为 PENDING，等待馆员审批。"""
    conn = get_conn()
    try:
        rp = _reader_of(conn, reader_user_id)
        reader_id = rp["reader_id"]

        if rp["credit_score"] < 60:
            raise AuthError("信用分过低，无法预约")
        if borrow_dao.has_unpaid_fine(conn, reader_id):
            raise AuthError("您有未结清的罚款，请先缴纳")

        book = book_dao.get_book(conn, book_id)
        if not book:
            raise AuthError("图书不存在", 404)

        # 有可借复本就不允许预约，直接去借
        if book["available_copies"] > 0:
            raise AuthError("该书有可借复本，请直接借阅，无需预约")

        if reservation_dao.has_queuing_reservation(conn, reader_id, book_id):
            raise AuthError("您已预约该书，请勿重复预约")

        if not borrow_days or borrow_days < 1:
            borrow_days = 30
        if borrow_days > 60:
            raise AuthError("借阅天数不能超过 60 天")

        rid = reservation_dao.create_reservation(conn, reader_id, book_id, borrow_days)
        user_dao.write_audit(conn, rp["user_id"], "RESERVE_REQUEST",
                             "book:%d" % book_id,
                             "borrow_days=%d" % borrow_days, "")
        conn.commit()
        return {"reservationId": rid, "status": "PENDING"}
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("reserve failed")
        raise
    finally:
        conn.close()


def list_pending():
    """馆员查看待审批的预约申请列表。"""
    conn = get_conn()
    try:
        rows = reservation_dao.list_pending_reservations(conn)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def approve(reservation_id, operator_id):
    """馆员审批通过预约，状态改为 QUEUING。"""
    conn = get_conn()
    try:
        r = reservation_dao.get_reservation(conn, reservation_id)
        if not r or r["status"] != "PENDING":
            raise AuthError("预约申请不存在或已处理", 404)
        reservation_dao.approve_reservation(conn, reservation_id)
        user_dao.write_audit(conn, operator_id, "RESERVE_APPROVE",
                             "reservation:%d" % reservation_id, "", "")
        conn.commit()
        return {"reservationId": reservation_id, "status": "QUEUING"}
    except AuthError:
        conn.rollback()
        raise
    finally:
        conn.close()


def reject(reservation_id, reason, operator_id):
    """馆员审批拒绝预约。"""
    conn = get_conn()
    try:
        r = reservation_dao.get_reservation(conn, reservation_id)
        if not r or r["status"] != "PENDING":
            raise AuthError("预约申请不存在或已处理", 404)
        reservation_dao.reject_reservation(conn, reservation_id, reason)
        user_dao.write_audit(conn, operator_id, "RESERVE_REJECT",
                             "reservation:%d" % reservation_id, reason, "")
        conn.commit()
        return {"reservationId": reservation_id, "status": "REJECTED"}
    except AuthError:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_reservation(reader_user_id, reservation_id):
    conn = get_conn()
    try:
        rp = _reader_of(conn, reader_user_id)
        r = reservation_dao.get_reservation(conn, reservation_id)
        if not r or r["reader_id"] != rp["reader_id"]:
            raise AuthError("预约记录不存在", 404)
        if r["status"] in ("FULFILLED", "CANCELLED", "EXPIRED"):
            raise AuthError("该预约已结束，无法取消")
        reservation_dao.cancel_reservation(conn, reservation_id)
        conn.commit()
        return {"reservationId": reservation_id, "status": "CANCELLED"}
    except AuthError:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_my_reservations(reader_user_id):
    conn = get_conn()
    try:
        rp = _reader_of(conn, reader_user_id)
        rows = reservation_dao.list_reservations_by_reader(conn, rp["reader_id"])
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_reservations_by_book(book_id):
    conn = get_conn()
    try:
        rows = reservation_dao.get_queuing_by_book(conn, book_id)
        return [dict(r) for r in rows]
    finally:
        conn.close()
