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


def reserve_book(reader_user_id, book_id):
    """读者预约某本书（需要没有可借复本，且没有未完成的同书预约）。"""
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

        rid = reservation_dao.create_reservation(conn, reader_id, book_id)
        queue_no = reservation_dao.get_reservation(conn, rid)["queue_no"]
        user_dao.write_audit(conn, rp["user_id"], "RESERVE",
                             "book:%d" % book_id,
                             "queue_no=%d" % queue_no, "")
        conn.commit()
        return {"reservationId": rid, "queueNo": queue_no}
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("reserve failed")
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
