# -*- coding: utf-8 -*-
"""预约借书的数据库访问。迭代二新增。"""
from datetime import datetime, timedelta

from src import config
from src.dao.user_dao import now_str


def get_next_queue_no(conn, book_id):
    row = conn.execute(
        "SELECT MAX(queue_no) AS m FROM reservation WHERE book_id = ?",
        (book_id,),
    ).fetchone()
    return (row["m"] or 0) + 1


def create_reservation(conn, reader_id, book_id):
    q = get_next_queue_no(conn, book_id)
    cur = conn.execute(
        """INSERT INTO reservation
           (reader_id, book_id, queue_no, status, created_at)
           VALUES (?, ?, ?, 'QUEUING', ?)""",
        (reader_id, book_id, q, now_str()),
    )
    return cur.lastrowid


def get_reservation(conn, reservation_id):
    return conn.execute(
        "SELECT * FROM reservation WHERE reservation_id = ?", (reservation_id,)
    ).fetchone()


def list_reservations_by_reader(conn, reader_id):
    return conn.execute(
        "SELECT * FROM reservation WHERE reader_id = ? ORDER BY created_at DESC",
        (reader_id,),
    ).fetchall()


def get_queuing_by_book(conn, book_id):
    return conn.execute(
        "SELECT * FROM reservation WHERE book_id = ? AND status = 'QUEUING' "
        "ORDER BY queue_no ASC",
        (book_id,),
    ).fetchall()


def get_head_reservation(conn, book_id):
    """取队首的预约（未被通知过的）。"""
    return conn.execute(
        "SELECT * FROM reservation WHERE book_id = ? AND status = 'QUEUING' "
        "ORDER BY queue_no ASC LIMIT 1",
        (book_id,),
    ).fetchone()


def ready_reservation(conn, reservation_id):
    ready = now_str()
    expire = (datetime.now() + timedelta(days=config.RESERVE_KEEP_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE reservation SET status = 'READY', ready_at = ?, expire_at = ? "
        "WHERE reservation_id = ?",
        (ready, expire, reservation_id),
    )


def fulfill_reservation(conn, reservation_id):
    conn.execute(
        "UPDATE reservation SET status = 'FULFILLED', fulfilled_at = ? "
        "WHERE reservation_id = ?",
        (now_str(), reservation_id),
    )


def expire_reservations(conn):
    # 超时未取的 READY 预约改为 EXPIRED，并顺延给下一位
    ts = now_str()
    conn.execute(
        "UPDATE reservation SET status = 'EXPIRED' "
        "WHERE status = 'READY' AND expire_at < ?",
        (ts,),
    )


def cancel_reservation(conn, reservation_id):
    conn.execute(
        "UPDATE reservation SET status = 'CANCELLED' WHERE reservation_id = ?",
        (reservation_id,),
    )


def has_queuing_reservation(conn, reader_id, book_id):
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM reservation "
        "WHERE reader_id = ? AND book_id = ? AND status IN ('QUEUING','READY')",
        (reader_id, book_id),
    ).fetchone()
    return row["c"] > 0
