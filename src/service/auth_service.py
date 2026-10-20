# -*- coding: utf-8 -*-
"""注册 / 登录 / 注销 业务逻辑。

迭代一只做账号这一块，借书还书这些在迭代二再加。
"""
from datetime import datetime

from src import config
from src.common import logger, security, validators
from src.dao import user_dao
from src.db.connection import get_conn

ROLE_NAME = {
    "READER": "读者",
    "LIBRARIAN": "图书馆管理员",
    "AUDITOR": "审核统计管理员",
}


class AuthError(Exception):
    """业务异常，code 用来给前端区分提示"""

    def __init__(self, message, code=400):
        super().__init__(message)
        self.message = message
        self.code = code


def _public_user(row):
    return {
        "userId": row["user_id"],
        "username": row["username"],
        "realName": row["real_name"],
        "role": row["role"],
        "roleName": ROLE_NAME.get(row["role"], row["role"]),
        "status": row["status"],
        "phone": row["phone"] or "",
    }


def register(username, password, real_name, phone="", reader_type="STUDENT", ip=""):
    """读者自助注册。馆员/审核员账号由审核统计管理员在后台创建，不开放注册。"""
    username = (username or "").strip()
    real_name = (real_name or "").strip()
    phone = (phone or "").strip()

    ok, msg = validators.check_username(username)
    if not ok:
        raise AuthError(msg)
    ok, msg = validators.check_real_name(real_name)
    if not ok:
        raise AuthError(msg)
    ok, msg = validators.check_phone(phone)
    if not ok:
        raise AuthError(msg)
    ok, msg = security.password_strength_ok(password)
    if not ok:
        raise AuthError(msg)

    conn = get_conn()
    try:
        exists = user_dao.find_user_by_name(conn, username)
        if exists:
            raise AuthError("该登录名已被注册")
        pwd_hash = security.make_password(password)
        user_id = user_dao.create_user(conn, username, pwd_hash, real_name, phone, "READER")
        # 读者证号先跟登录名一致；后面馆员可以改
        user_dao.create_reader_profile(conn, user_id, username, reader_type)
        user_dao.write_audit(conn, user_id, "REGISTER", "user:%d" % user_id,
                             "reader_type=%s" % reader_type, ip)
        conn.commit()
        logger.info("register ok user=%s role=READER ip=%s" % (username, ip))
        row = user_dao.find_user_by_id(conn, user_id)
        return _public_user(row)
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("register failed user=%s" % username)
        raise
    finally:
        conn.close()


def login(username, password, ip=""):
    username = (username or "").strip()
    if not username or not password:
        raise AuthError("请输入登录名和口令")

    conn = get_conn()
    try:
        row = user_dao.find_user_by_name(conn, username)
        if row is None:
            user_dao.write_audit(conn, None, "LOGIN_FAIL", "username:%s" % username,
                                 "用户不存在", ip, "FAIL")
            conn.commit()
            raise AuthError("登录名或口令错误")

        if row["status"] == "FROZEN":
            user_dao.write_audit(conn, row["user_id"], "LOGIN_FAIL", "user:%d" % row["user_id"],
                                 "账号冻结", ip, "FAIL")
            conn.commit()
            raise AuthError("账号已被冻结，请联系图书馆管理员", 403)

        # 锁定期内直接拒绝，不再累加失败次数，防止把锁定时间越拖越长
        if row["lock_until"]:
            lock_until = datetime.strptime(row["lock_until"], "%Y-%m-%d %H:%M:%S")
            if lock_until > datetime.now():
                left = int((lock_until - datetime.now()).total_seconds() // 60) + 1
                raise AuthError("连续登录失败次数过多，请 %d 分钟后再试" % left, 429)

        if not security.check_password(password, row["password_hash"]):
            fails = user_dao.add_fail_count(conn, row["user_id"])
            if fails >= config.LOGIN_FAIL_LIMIT:
                user_dao.lock_user(conn, row["user_id"], config.LOCK_MINUTES)
                user_dao.write_audit(conn, row["user_id"], "LOGIN_FAIL",
                                     "user:%d" % row["user_id"], "连续失败锁定", ip, "FAIL")
                conn.commit()
                raise AuthError("连续 %d 次口令错误，账号已锁定 %d 分钟"
                                % (config.LOGIN_FAIL_LIMIT, config.LOCK_MINUTES), 429)
            user_dao.write_audit(conn, row["user_id"], "LOGIN_FAIL", "user:%d" % row["user_id"],
                                 "口令错误(%d/%d)" % (fails, config.LOGIN_FAIL_LIMIT), ip, "FAIL")
            conn.commit()
            raise AuthError("登录名或口令错误")

        token = security.new_token()
        user_dao.clean_expired_session(conn)
        # 登录成功才清失败计数，避免一次失败就把前面的记录抹掉
        user_dao.clear_login_fail(conn, row["user_id"])
        expire_at = user_dao.create_session(conn, token, row["user_id"], config.SESSION_MINUTES)
        user_dao.write_audit(conn, row["user_id"], "LOGIN", "user:%d" % row["user_id"],
                             "登录成功", ip)
        conn.commit()
        logger.info("login ok user=%s role=%s ip=%s" % (username, row["role"], ip))
        return {"token": token, "expireAt": expire_at, "user": _public_user(row)}
    finally:
        conn.close()


def logout(token, ip=""):
    if not token:
        return
    conn = get_conn()
    try:
        session = user_dao.find_session(conn, token)
        if session:
            user_dao.write_audit(conn, session["user_id"], "LOGOUT",
                                 "user:%d" % session["user_id"], "", ip)
            user_dao.delete_session(conn, token)
            conn.commit()
    finally:
        conn.close()


def current_user(token):
    """根据令牌取当前登录用户，过期或不存在返回 None"""
    if not token:
        return None
    conn = get_conn()
    try:
        session = user_dao.find_session(conn, token)
        if session is None:
            return None
        expire_at = datetime.strptime(session["expire_at"], "%Y-%m-%d %H:%M:%S")
        if expire_at <= datetime.now():
            user_dao.delete_session(conn, token)
            conn.commit()
            return None
        row = user_dao.find_user_by_id(conn, session["user_id"])
        if row is None or row["status"] == "FROZEN":
            return None
        return _public_user(row)
    finally:
        conn.close()
