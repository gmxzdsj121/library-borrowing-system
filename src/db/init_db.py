# -*- coding: utf-8 -*-
"""初始化数据库并写入演示账号。可以重复执行，已有数据不会覆盖。"""
import os
import sys

# 允许直接用 python src/db/init_db.py 跑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import security  # noqa: E402
from src.dao import user_dao, book_dao  # noqa: E402
from src.db.connection import get_conn, init_schema  # noqa: E402


SEED_USERS = [
    # username, password, real_name, role
    ("libadmin", "lib123456", "馆员-张老师", "LIBRARIAN"),
    ("auditor", "audit123456", "审核员-李老师", "AUDITOR"),
    ("reader01", "reader123456", "读者-王同学", "READER"),
]

# 迭代二加一些示例图书，方便联调
SEED_BOOKS = [
    # isbn, title, author, publisher, year, price, [barcode...]
    ("9787111618637", "软件工程导论（第5版）", "张海藩", "人民邮电出版社", 2018, 49.0, ["BC1001", "BC1002"]),
    ("9787040406641", "数据库系统概论（第5版）", "王珊", "高等教育出版社", 2014, 43.5, ["BC2001"]),
    ("9787115428028", "Python 编程：从入门到实践", "Eric Matthes", "人民邮电出版社", 2016, 89.0, ["BC3001", "BC3002", "BC3003"]),
    ("9787111407010", "计算机网络：自顶向下方法", "James F. Kurose", "机械工业出版社", 2014, 79.0, ["BC4001"]),
]


def seed():
    init_schema()
    conn = get_conn()
    try:
        exists = conn.execute("SELECT COUNT(*) AS c FROM sys_user").fetchone()["c"]
        if not exists:
            for username, pwd, real_name, role in SEED_USERS:
                uid = user_dao.create_user(conn, username, security.make_password(pwd),
                                           real_name, "", role)
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

        print("数据库初始化完成：", os.path.abspath(__import__("src.config", fromlist=["DB_PATH"]).DB_PATH))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
