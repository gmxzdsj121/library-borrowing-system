# -*- coding: utf-8 -*-
"""通知公告服务：满足 FR-13 通知与公告需求。
馆员与审核员可发布公告，所有读者可见；系统自动生成到书通知。"""
from src.db.connection import get_conn
from src.dao.user_dao import now_str


def create_notice(title, content, operator_id, notice_type="ANNOUNCE"):
    """发布公告。"""
    conn = get_conn()
    conn.execute(
        """INSERT INTO notice (user_id, title, content, type, is_read, created_at)
           VALUES (?, ?, ?, ?, 0, ?)""",
        (operator_id, title, content, notice_type, now_str()))
    conn.commit()
    conn.close()
    return {"title": title, "type": notice_type}


def list_notices(user_id, limit=20):
    """列出通知公告，到书通知只推送给相关读者。"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT notice_id, title, content, type, is_read, created_at
           FROM notice
           WHERE type = 'ANNOUNCE' OR (type = 'RESERVE' AND user_id = ?)
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit)).fetchall()
    conn.close()
    return [{"id": r["notice_id"], "title": r["title"], "content": r["content"],
             "type": r["type"], "isRead": r["is_read"], "createdAt": r["created_at"]}
            for r in rows]


def mark_read(notice_id, user_id):
    """标记为已读。"""
    conn = get_conn()
    conn.execute("UPDATE notice SET is_read = 1 WHERE notice_id = ?", (notice_id,))
    conn.commit()
    conn.close()
    return True


def push_ready_notice(user_id, book_title):
    """预约到书时自动推送一条通知。"""
    conn = get_conn()
    conn.execute(
        """INSERT INTO notice (user_id, title, content, type, is_read, created_at)
           VALUES (?, ?, ?, 'RESERVE', 0, ?)""",
        (user_id, "预约图书到馆", "您预约的《%s》已到馆，请尽快借阅。" % book_title,
         now_str()))
    conn.commit()
    conn.close()
