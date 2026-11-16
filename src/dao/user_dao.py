# -*- coding: utf-8 -*-
"""用户、会话、日志的数据库访问。SQL 都集中在这里，service 层不直接写 SQL。"""
from datetime import datetime, timedelta

from src import config


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def find_user_by_name(conn, username):
    return conn.execute(
        "SELECT * FROM sys_user WHERE username = ?", (username,)
    ).fetchone()


def find_user_by_login(conn, login_name):
    """支持用户名或纯数字账号ID登录。"""
    if login_name.isdigit():
        row = conn.execute(
            "SELECT * FROM sys_user WHERE user_id = ?", (int(login_name),)
        ).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT * FROM sys_user WHERE username = ?", (login_name,)
    ).fetchone()


def find_user_by_id(conn, user_id):
    return conn.execute(
        "SELECT * FROM sys_user WHERE user_id = ?", (user_id,)
    ).fetchone()


def update_profile(conn, user_id, real_name=None, phone=None):
    sets = []
    vals = []
    if real_name is not None:
        sets.append("real_name = ?")
        vals.append(real_name)
    if phone is not None:
        sets.append("phone = ?")
        vals.append(phone)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(now_str())
    vals.append(user_id)
    conn.execute("UPDATE sys_user SET %s WHERE user_id = ?" % ", ".join(sets), vals)


def change_password(conn, user_id, new_password_hash):
    conn.execute(
        "UPDATE sys_user SET password_hash = ?, updated_at = ? WHERE user_id = ?",
        (new_password_hash, now_str(), user_id),
    )


def create_user(conn, username, password_hash, real_name, phone, role="READER"):
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO sys_user
           (username, password_hash, real_name, role, status, phone, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?)""",
        (username, password_hash, real_name, role, phone, ts, ts),
    )
    return cur.lastrowid


def create_reader_profile(conn, user_id, reader_no, reader_type="STUDENT"):
    conn.execute(
        """INSERT INTO reader_profile
           (user_id, reader_no, reader_type, max_borrow, credit_score, created_at)
           VALUES (?, ?, ?, ?, 100, ?)""",
        (user_id, reader_no, reader_type, config.MAX_BORROW, now_str()),
    )


def add_fail_count(conn, user_id):
    conn.execute(
        "UPDATE sys_user SET fail_count = fail_count + 1, updated_at = ? WHERE user_id = ?",
        (now_str(), user_id),
    )
    row = find_user_by_id(conn, user_id)
    return row["fail_count"]


def lock_user(conn, user_id, minutes):
    until = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE sys_user SET lock_until = ?, updated_at = ? WHERE user_id = ?",
        (until, now_str(), user_id),
    )
    return until


def clear_login_fail(conn, user_id):
    conn.execute(
        """UPDATE sys_user
           SET fail_count = 0, lock_until = NULL, last_login_at = ?, updated_at = ?
           WHERE user_id = ?""",
        (now_str(), now_str(), user_id),
    )


def create_session(conn, token, user_id, minutes):
    created = now_str()
    expire = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO sys_session (token, user_id, created_at, expire_at) VALUES (?, ?, ?, ?)",
        (token, user_id, created, expire),
    )
    return expire


def find_session(conn, token):
    return conn.execute(
        "SELECT * FROM sys_session WHERE token = ?", (token,)
    ).fetchone()


def delete_session(conn, token):
    conn.execute("DELETE FROM sys_session WHERE token = ?", (token,))


def clean_expired_session(conn):
    conn.execute("DELETE FROM sys_session WHERE expire_at < ?", (now_str(),))


def write_audit(conn, user_id, action, target="", detail="", ip="", result="OK"):
    conn.execute(
        """INSERT INTO sys_audit_log
           (user_id, action, target, detail, ip, result, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, action, target, detail, ip, result, now_str()),
    )
