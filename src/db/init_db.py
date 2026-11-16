# -*- coding: utf-8 -*-
"""初始化数据库并写入演示账号。可以重复执行，已有数据不会覆盖。"""
import os
import sys
from datetime import datetime, timedelta

# 允许直接用 python src/db/init_db.py 跑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import security  # noqa: E402
from src.dao import user_dao, book_dao, borrow_dao, reservation_dao  # noqa: E402
from src.db.connection import get_conn, init_schema  # noqa: E402


SEED_USERS = [
    # username, password, real_name, role, phone
    ("libadmin", "lib123456", "馆员-张老师", "LIBRARIAN", "13800000001"),
    ("auditor", "audit123456", "审核员-李老师", "AUDITOR", "13800000002"),
    ("reader01", "reader123456", "读者-王同学", "READER", "13900000001"),
    ("reader02", "reader123456", "读者-李同学", "READER", "13900000002"),
    ("reader03", "reader123456", "读者-赵同学", "READER", "13900000003"),
]

# 迭代二加一些示例图书，方便联调
SEED_BOOKS = [
    # isbn, title, author, publisher, year, price, [barcode...]
    ("9787111618637", "软件工程导论（第5版）", "张海藩", "人民邮电出版社", 2018, 49.0, ["BC1001", "BC1002"]),
    ("9787040406641", "数据库系统概论（第5版）", "王珊", "高等教育出版社", 2014, 43.5, ["BC2001"]),
    ("9787115428028", "Python 编程：从入门到实践", "Eric Matthes", "人民邮电出版社", 2016, 89.0, ["BC3001", "BC3002", "BC3003"]),
    ("9787111407010", "计算机网络：自顶向下方法", "James F. Kurose", "机械工业出版社", 2014, 79.0, ["BC4001"]),
    ("9787111213826", "数据结构（C语言版）", "严蔚敏", "清华大学出版社", 2007, 35.0, ["BC5001", "BC5002"]),
]


def migrate_columns(conn):
    """迭代三新增字段迁移：reservation 表加 borrow_days、reject_reason。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(reservation)").fetchall()}
    if "borrow_days" not in cols:
        conn.execute("ALTER TABLE reservation ADD COLUMN borrow_days INTEGER NOT NULL DEFAULT 30")
        print("迁移：reservation.borrow_days 已添加")
    if "reject_reason" not in cols:
        conn.execute("ALTER TABLE reservation ADD COLUMN reject_reason TEXT")
        print("迁移：reservation.reject_reason 已添加")
    conn.commit()


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def seed_demo_data(conn):
    """注入演示数据：借阅中、逾期未还、罚款、预约。仅在无借阅记录时执行。"""
    cnt = conn.execute("SELECT COUNT(*) AS c FROM borrow_record").fetchone()["c"]
    if cnt > 0:
        print("已有借阅记录，跳过演示数据注入")
        return

    now = datetime.now()
    # 找到读者和馆员
    readers = {}
    for row in conn.execute("SELECT u.user_id, u.username, rp.reader_id FROM sys_user u "
                            "JOIN reader_profile rp ON u.user_id = rp.user_id "
                            "WHERE u.role = 'READER'").fetchall():
        readers[row["username"]] = (row["user_id"], row["reader_id"])

    lib_user = conn.execute("SELECT user_id FROM sys_user WHERE role = 'LIBRARIAN' LIMIT 1").fetchone()
    lib_id = lib_user["user_id"] if lib_user else 1

    # 找到图书复本
    copies = {}
    for row in conn.execute("SELECT bc.copy_id, bc.barcode, bc.book_id, b.title FROM book_copy bc "
                            "JOIN book b ON bc.book_id = b.book_id").fetchall():
        copies[row["barcode"]] = (row["copy_id"], row["book_id"], row["title"])

    def _borrow(reader_key, barcode, days_ago, due_days):
        """创建一条借阅记录，days_ago 天前借出，due_days 天应还。"""
        uid, rid = readers[reader_key]
        copy_id, book_id, title = copies[barcode]
        borrow_at = now - timedelta(days=days_ago)
        due_at = borrow_at + timedelta(days=due_days)
        rec_id = conn.execute(
            """INSERT INTO borrow_record (reader_id, copy_id, borrow_at, due_at, renew_count, status, operator_id, created_at)
               VALUES (?, ?, ?, ?, 0, 'BORROWED', ?, ?)""",
            (rid, copy_id, _fmt(borrow_at), _fmt(due_at), lib_id, _fmt(borrow_at))
        ).lastrowid
        # 复本状态改为 BORROWED，可借数 -1
        conn.execute("UPDATE book_copy SET status = 'BORROWED' WHERE copy_id = ?", (copy_id,))
        conn.execute("UPDATE book SET available_copies = available_copies - 1 WHERE book_id = ?", (book_id,))
        return rec_id, rid, due_at

    # 1) reader01 正常借阅中：软件工程导论，10天前借，30天还（未到期）
    _borrow("reader01", "BC1001", days_ago=10, due_days=30)

    # 2) reader02 逾期未还：数据库系统概论，40天前借，30天还（已逾期10天）
    rec_id, rid, due_at = _borrow("reader02", "BC2001", days_ago=40, due_days=30)
    conn.execute("UPDATE borrow_record SET status = 'OVERDUE' WHERE record_id = ?", (rec_id,))
    # 生成罚款：逾期10天，宽限期3天，罚7天 * 0.5 = 3.5元
    overdue = 10 - 3  # FINE_FREE_DAYS=3
    conn.execute(
        """INSERT INTO fine_record (record_id, reader_id, overdue_days, amount, status, created_at)
           VALUES (?, ?, ?, ?, 'UNPAID', ?)""",
        (rec_id, rid, overdue, round(overdue * 0.5, 2), _fmt(now))
    )
    # 信用分扣5
    conn.execute("UPDATE reader_profile SET credit_score = credit_score - 5 WHERE reader_id = ?", (rid,))

    # 3) reader03 逾期未还且已缴罚款：Python编程，35天前借，30天还（逾期5天，罚1元已缴）
    rec_id3, rid3, due_at3 = _borrow("reader03", "BC3001", days_ago=35, due_days=30)
    conn.execute("UPDATE borrow_record SET status = 'OVERDUE' WHERE record_id = ?", (rec_id3,))
    overdue3 = 5 - 3
    conn.execute(
        """INSERT INTO fine_record (record_id, reader_id, overdue_days, amount, status, created_at, paid_at, operator_id)
           VALUES (?, ?, ?, ?, 'PAID', ?, ?, ?)""",
        (rec_id3, rid3, overdue3, round(overdue3 * 0.5, 2), _fmt(now), _fmt(now), lib_id)
    )

    # 4) reader01 有一条待审批的预约申请：数据结构（book_id 需查）
    ds_book = conn.execute("SELECT book_id FROM book WHERE title LIKE '%数据结构%'").fetchone()
    if ds_book and "reader01" in readers:
        uid01, rid01 = readers["reader01"]
        q = conn.execute("SELECT COALESCE(MAX(queue_no),0)+1 AS m FROM reservation WHERE book_id = ?",
                         (ds_book["book_id"],)).fetchone()["m"]
        conn.execute(
            """INSERT INTO reservation (reader_id, book_id, queue_no, borrow_days, status, created_at)
               VALUES (?, ?, ?, 30, 'PENDING', ?)""",
            (rid01, ds_book["book_id"], q, _fmt(now))
        )

    conn.commit()
    print("演示数据已注入：2条借阅中、2条逾期（1条未缴罚款1条已缴）、1条待审批预约")


def seed():
    init_schema()
    conn = get_conn()
    try:
        migrate_columns(conn)

        exists = conn.execute("SELECT COUNT(*) AS c FROM sys_user").fetchone()["c"]
        if not exists:
            for username, pwd, real_name, role, phone in SEED_USERS:
                uid = user_dao.create_user(conn, username, security.make_password(pwd),
                                           real_name, phone, role)
                if role == "READER":
                    user_dao.create_reader_profile(conn, uid, username, "STUDENT")
                print("创建账号：%s / %s（%s）" % (username, pwd, role))
            conn.commit()
        else:
            print("已有 %d 个账号，跳过账号初始化" % exists)

        # 图书种子：没有书才加
        book_count = conn.execute("SELECT COUNT(*) AS c FROM book").fetchone()["c"]
        if book_count == 0:
            for isbn, title, author, pub, year, price, codes in SEED_BOOKS:
                bid = book_dao.create_book(conn, isbn, title, author, pub, year, None, price)
                for code in codes:
                    book_dao.create_copy(conn, bid, code, "A区")
                print("导入图书：%s（%d 册）" % (title, len(codes)))
            conn.commit()
        else:
            print("已有 %d 条书目，跳过图书种子" % book_count)

        # 演示业务数据
        seed_demo_data(conn)

        print("数据库初始化完成：", os.path.abspath(__import__("src.config", fromlist=["DB_PATH"]).DB_PATH))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
