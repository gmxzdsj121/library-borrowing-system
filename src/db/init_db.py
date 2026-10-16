# -*- coding: utf-8 -*-
"""初始化数据库并写入演示账号。可以重复执行，已有数据不会覆盖。"""
import os
import sys

# 允许直接用 python src/db/init_db.py 跑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import security  # noqa: E402
from src.dao import user_dao  # noqa: E402
from src.db.connection import get_conn, init_schema  # noqa: E402


SEED_USERS = [
    # username, password, real_name, role
    ("libadmin", "lib123456", "馆员-张老师", "LIBRARIAN"),
    ("auditor", "audit123456", "审核员-李老师", "AUDITOR"),
    ("reader01", "reader123456", "读者-王同学", "READER"),
]


def seed():
    init_schema()
    conn = get_conn()
    try:
        exists = conn.execute("SELECT COUNT(*) AS c FROM sys_user").fetchone()["c"]
        if exists:
            print("已有 %d 个账号，跳过初始化" % exists)
            return
        for username, pwd, real_name, role in SEED_USERS:
            uid = user_dao.create_user(conn, username, security.make_password(pwd),
                                       real_name, "", role)
            if role == "READER":
                user_dao.create_reader_profile(conn, uid, username, "STUDENT")
            print("创建账号：%s / %s（%s）" % (username, pwd, role))
        conn.commit()
        print("数据库初始化完成：", os.path.abspath(__import__("src.config", fromlist=["DB_PATH"]).DB_PATH))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
