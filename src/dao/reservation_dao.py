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


def create_reservation(conn, reader_id, book_id, borrow_days=30):
    q = get_next_queue_no(conn, book_id)
    cur = conn.execute(
        """INSERT INTO reservation
           (reader_id, book_id, queue_no, borrow_days, status, created_at)
           VALUES (?, ?, ?, ?, 'PENDING', ?)""",
        (reader_id, book_id, q, borrow_days, now_str()),
    )
    return cur.lastrowid


def get_reservation(conn, reservation_id):
    return conn.execute(
        "SELECT * FROM reservation WHERE reservation_id = ?", (reservation_id,)
    ).fetchone()


def list_reservations_by_reader(conn, reader_id):
    """列出读者的所有预约，关联图书表拿到书名和ISBN。"""
    return conn.execute(
        """SELECT r.*, b.title, b.isbn
           FROM reservation r
           JOIN book b ON r.book_id = b.book_id
           WHERE r.reader_id = ? ORDER BY r.created_at DESC""",
        (reader_id,),
    ).fetchall()


def list_pending_reservations(conn):
    """列出所有待审批的预约申请，含读者与图书信息。"""
    return conn.execute(
        """SELECT r.*, u.username, u.real_name, b.title, b.isbn
           FROM reservation r
           JOIN reader_profile rp ON r.reader_id = rp.reader_id
           JOIN sys_user u ON rp.user_id = u.user_id
           JOIN book b ON r.book_id = b.book_id
           WHERE r.status = 'PENDING'
           ORDER BY r.created_at ASC"""
    ).fetchall()


def approve_reservation(conn, reservation_id):
    """审批通过：状态从 PENDING 改为 QUEUING（进入预约队列）。"""
    conn.execute(
        "UPDATE reservation SET status = 'QUEUING' WHERE reservation_id = ? AND status = 'PENDING'",
        (reservation_id,),
    )


def reject_reservation(conn, reservation_id, reason=""):
    """审批拒绝。"""
    conn.execute(
        "UPDATE reservation SET status = 'REJECTED', reject_reason = ? "
        "WHERE reservation_id = ? AND status = 'PENDING'",
        (reason, reservation_id),
    )


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
        "WHERE reader_id = ? AND book_id = ? AND status IN ('PENDING','QUEUING','READY')",
        (reader_id, book_id),
    ).fetchone()
    return row["c"] > 0
