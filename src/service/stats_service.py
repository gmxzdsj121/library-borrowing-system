# -*- coding: utf-8 -*-
"""统计报表服务：满足 FR-12 借阅统计报表需求。
统计接口对审核统计管理员开放，包含馆藏概况、借阅趋势、热门图书、罚款汇总。"""
from src.db.connection import get_conn


def overview():
    """馆藏与借阅整体概况：图书数、复本数、在借数、读者数、逾期数。"""
    conn = get_conn()
    cur = conn.execute("SELECT COUNT(*) AS n FROM book")
    book_total = cur.fetchone()["n"]
    cur = conn.execute("SELECT COUNT(*) AS n FROM book_copy")
    copy_total = cur.fetchone()["n"]
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM borrow_record WHERE status = 'BORROWED'")
    borrowed = cur.fetchone()["n"]
    cur = conn.execute("SELECT COUNT(*) AS n FROM reader_profile")
    reader_total = cur.fetchone()["n"]
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM borrow_record "
        "WHERE status = 'BORROWED' AND due_at < ?", (_now(),))
    overdue = cur.fetchone()["n"]
    conn.close()
    return {
        "bookTotal": book_total,
        "copyTotal": copy_total,
        "borrowed": borrowed,
        "readerTotal": reader_total,
        "overdue": overdue,
        "available": copy_total - borrowed,
    }


def borrow_trend(days=30):
    """按天统计最近 N 天的借书与归还量，用于折线图。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT substr(borrow_at, 1, 10) AS d, COUNT(*) AS n "
        "FROM borrow_record WHERE borrow_at >= date('now', ?) "
        "GROUP BY d ORDER BY d", ("-%d days" % days,)).fetchall()
    borrow_by_day = {r["d"]: r["n"] for r in rows}
    rows = conn.execute(
        "SELECT substr(return_at, 1, 10) AS d, COUNT(*) AS n "
        "FROM borrow_record WHERE return_at IS NOT NULL "
        "AND return_at >= date('now', ?) GROUP BY d ORDER BY d",
        ("-%d days" % days,)).fetchall()
    return_by_day = {r["d"]: r["n"] for r in rows}
    conn.close()
    # 补齐没有记录的日期，避免图表断层
    dates = _date_range(days)
    return [{"date": d, "borrow": borrow_by_day.get(d, 0),
             "return": return_by_day.get(d, 0)} for d in dates]


def popular_books(top=10):
    """热门图书榜：按借阅次数倒序取前 N。"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT b.title, b.author, COUNT(br.record_id) AS times
           FROM borrow_record br
           JOIN book_copy bc ON br.copy_id = bc.copy_id
           JOIN book b ON bc.book_id = b.book_id
           GROUP BY b.book_id ORDER BY times DESC LIMIT ?""", (top,)).fetchall()
    conn.close()
    return [{"title": r["title"], "author": r["author"],
             "borrowTimes": r["times"]} for r in rows]


def fine_summary():
    """罚款汇总：总罚款、已缴、未缴、减免。"""
    conn = get_conn()
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM fine_record").fetchone()["s"]
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM fine_record "
        "WHERE status = 'PAID'").fetchone()["s"]
    unpaid = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM fine_record "
        "WHERE status = 'UNPAID'").fetchone()["s"]
    waived = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM fine_record "
        "WHERE status = 'WAIVED'").fetchone()["s"]
    conn.close()
    return {"total": round(total, 2), "paid": round(paid, 2),
            "unpaid": round(unpaid, 2), "waived": round(waived, 2)}


def _now():
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _date_range(days):
    import datetime
    today = datetime.date.today()
    return [(today - datetime.timedelta(days=i)).isoformat()
            for i in range(days - 1, -1, -1)]
