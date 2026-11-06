# -*- coding: utf-8 -*-
"""借阅记录与罚款的数据库访问。迭代二新增。"""
from datetime import datetime, timedelta

from src import config
from src.dao.user_dao import now_str


def create_borrow(conn, reader_id, copy_id, due_at, operator_id):
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO borrow_record
           (reader_id, copy_id, borrow_at, due_at, renew_count, status,
            operator_id, created_at)
           VALUES (?, ?, ?, ?, 0, 'BORROWED', ?, ?)""",
        (reader_id, copy_id, ts, due_at, operator_id, ts),
    )
    return cur.lastrowid


def get_borrow(conn, record_id):
    return conn.execute(
        "SELECT * FROM borrow_record WHERE record_id = ?", (record_id,)
    ).fetchone()


def get_active_borrows_by_reader(conn, reader_id):
    return conn.execute(
        "SELECT * FROM borrow_record WHERE reader_id = ? AND status != 'RETURNED' "
        "ORDER BY borrow_at DESC",
        (reader_id,),
    ).fetchall()


def get_borrows_by_reader(conn, reader_id):
    # 包括已归还的，给"我的借阅"页面用
    return conn.execute(
        "SELECT * FROM borrow_record WHERE reader_id = ? ORDER BY borrow_at DESC",
        (reader_id,),
    ).fetchall()


def return_borrow(conn, record_id, return_at=None):
    ts = return_at or now_str()
    conn.execute(
        "UPDATE borrow_record SET return_at = ?, status = 'RETURNED' "
        "WHERE record_id = ?",
        (ts, record_id),
    )


def mark_overdue(conn, record_id):
    # 状态从 BORROWED 改成 OVERDUE，后续定时或归还时触发
    conn.execute(
        "UPDATE borrow_record SET status = 'OVERDUE' WHERE record_id = ? AND status = 'BORROWED'",
        (record_id,),
    )


def renew_borrow(conn, record_id, new_due_at):
    conn.execute(
        "UPDATE borrow_record SET renew_count = renew_count + 1, due_at = ? "
        "WHERE record_id = ?",
        (new_due_at, record_id),
    )


def count_active_borrows(conn, reader_id):
    return conn.execute(
        "SELECT COUNT(*) AS c FROM borrow_record "
        "WHERE reader_id = ? AND status != 'RETURNED'",
        (reader_id,),
    ).fetchone()["c"]


def has_overdue(conn, reader_id):
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM borrow_record "
        "WHERE reader_id = ? AND status = 'OVERDUE'",
        (reader_id,),
    ).fetchone()
    return row["c"] > 0


# ---------- 罚款 ----------
def create_fine(conn, record_id, reader_id, overdue_days, amount):
    cur = conn.execute(
        """INSERT INTO fine_record
           (record_id, reader_id, overdue_days, amount, status, created_at)
           VALUES (?, ?, ?, ?, 'UNPAID', ?)""",
        (record_id, reader_id, overdue_days, amount, now_str()),
    )
    return cur.lastrowid


def get_fine(conn, fine_id):
    return conn.execute(
        "SELECT * FROM fine_record WHERE fine_id = ?", (fine_id,)
    ).fetchone()


def list_fines_by_reader(conn, reader_id, status=None):
    if status:
        return conn.execute(
            "SELECT * FROM fine_record WHERE reader_id = ? AND status = ? "
            "ORDER BY created_at DESC",
            (reader_id, status),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM fine_record WHERE reader_id = ? ORDER BY created_at DESC",
        (reader_id,),
    ).fetchall()


def pay_fine(conn, fine_id, operator_id):
    conn.execute(
        "UPDATE fine_record SET status = 'PAID', paid_at = ?, operator_id = ? "
        "WHERE fine_id = ?",
        (now_str(), operator_id, fine_id),
    )


def waive_fine(conn, fine_id, operator_id):
    # 减免需要审核统计管理员，调用方已经做了角色校验
    conn.execute(
        "UPDATE fine_record SET status = 'WAIVED', operator_id = ? "
        "WHERE fine_id = ?",
        (operator_id, fine_id),
    )


def has_unpaid_fine(conn, reader_id):
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM fine_record "
        "WHERE reader_id = ? AND status = 'UNPAID'",
        (reader_id,),
    ).fetchone()
    return row["c"] > 0


def compute_overdue_days(due_at_str, return_at_str=None):
    """计算逾期天数，扣除宽限期，不足为 0。"""
    fmt = "%Y-%m-%d %H:%M:%S"
    due = datetime.strptime(due_at_str, fmt)
    now = datetime.strptime(return_at_str, fmt) if return_at_str else datetime.now()
    delta = (now - due).total_seconds()
    if delta <= 0:
        return 0
    days = int(delta // 86400)
    if days <= config.FINE_FREE_DAYS:
        return 0
    return days - config.FINE_FREE_DAYS


def compute_fine_amount(overdue_days):
    return round(overdue_days * config.FINE_PER_DAY, 2)
