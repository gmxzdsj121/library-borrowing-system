# -*- coding: utf-8 -*-
"""图书、分类、馆藏复本的数据库访问。迭代二新增。

约定：所有写操作的事务（commit/rollback）由 service 层控制，这里只执行 SQL。
"""
from src.dao.user_dao import now_str


# ---------- 分类 ----------
def list_categories(conn):
    return conn.execute(
        "SELECT * FROM book_category ORDER BY sort_no, category_id"
    ).fetchall()


def get_category(conn, category_id):
    return conn.execute(
        "SELECT * FROM book_category WHERE category_id = ?", (category_id,)
    ).fetchone()


def create_category(conn, name, parent_id=None, sort_no=0):
    cur = conn.execute(
        "INSERT INTO book_category (name, parent_id, sort_no) VALUES (?, ?, ?)",
        (name, parent_id, sort_no),
    )
    return cur.lastrowid


# ---------- 书目 ----------
def list_books(conn, keyword=None, category_id=None, page=1, page_size=20):
    sql = "SELECT * FROM book WHERE 1=1"
    args = []
    if keyword:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        kw = "%%%s%%" % keyword
        args += [kw, kw, kw]
    if category_id:
        sql += " AND category_id = ?"
        args.append(category_id)
    sql += " ORDER BY book_id DESC LIMIT ? OFFSET ?"
    args.append(page_size)
    args.append((page - 1) * page_size)
    return conn.execute(sql, args).fetchall()


def count_books(conn, keyword=None, category_id=None):
    sql = "SELECT COUNT(*) AS c FROM book WHERE 1=1"
    args = []
    if keyword:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        kw = "%%%s%%" % keyword
        args += [kw, kw, kw]
    if category_id:
        sql += " AND category_id = ?"
        args.append(category_id)
    return conn.execute(sql, args).fetchone()["c"]


def get_book(conn, book_id):
    return conn.execute(
        "SELECT b.*, c.name AS category_name FROM book b "
        "LEFT JOIN book_category c ON b.category_id = c.category_id "
        "WHERE b.book_id = ?",
        (book_id,),
    ).fetchone()


def get_book_by_isbn(conn, isbn):
    return conn.execute(
        "SELECT * FROM book WHERE isbn = ?", (isbn,)
    ).fetchone()


def create_book(conn, isbn, title, author, publisher, publish_year,
                category_id, price):
    ts = now_str()
    cur = conn.execute(
        """INSERT INTO book
           (isbn, title, author, publisher, publish_year, category_id, price,
            total_copies, available_copies, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 'ON_SHELF', ?, ?)""",
        (isbn, title, author, publisher, publish_year, category_id, price, ts, ts),
    )
    return cur.lastrowid


def update_book(conn, book_id, **fields):
    # 10-28: 用拼接 SQL 最省事，字段白名单在 service 里已经卡过了
    allowed = ("isbn", "title", "author", "publisher", "publish_year",
               "category_id", "price", "status")
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            sets.append("%s = ?" % k)
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(now_str())
    vals.append(book_id)
    conn.execute("UPDATE book SET %s WHERE book_id = ?" % ", ".join(sets), vals)


# ---------- 馆藏复本 ----------
def list_copies_by_book(conn, book_id):
    return conn.execute(
        "SELECT * FROM book_copy WHERE book_id = ? ORDER BY copy_id", (book_id,)
    ).fetchall()


def get_copy(conn, copy_id):
    return conn.execute(
        "SELECT * FROM book_copy WHERE copy_id = ?", (copy_id,)
    ).fetchone()


def get_copy_by_barcode(conn, barcode):
    return conn.execute(
        "SELECT * FROM book_copy WHERE barcode = ?", (barcode,)
    ).fetchone()


def create_copy(conn, book_id, barcode, location=""):
    cur = conn.execute(
        """INSERT INTO book_copy (book_id, barcode, location, status, created_at)
           VALUES (?, ?, ?, 'AVAILABLE', ?)""",
        (book_id, barcode, location, now_str()),
    )
    # 复本数 +1，可借数 +1
    conn.execute(
        """UPDATE book SET total_copies = total_copies + 1,
           available_copies = available_copies + 1, updated_at = ?
           WHERE book_id = ?""",
        (now_str(), book_id),
    )
    return cur.lastrowid


def set_copy_status(conn, copy_id, status):
    conn.execute(
        "UPDATE book_copy SET status = ? WHERE copy_id = ?", (status, copy_id)
    )


def adjust_available(conn, book_id, delta):
    """调整可借复本数（借书 -1，归还 +1，预约保留 0 不动）"""
    conn.execute(
        "UPDATE book SET available_copies = available_copies + ?, updated_at = ? "
        "WHERE book_id = ?",
        (delta, now_str(), book_id),
    )


# ---------- 读者档案 ----------
def get_reader_profile(conn, user_id):
    return conn.execute(
        "SELECT * FROM reader_profile WHERE user_id = ?", (user_id,)
    ).fetchone()


def get_reader_profile_by_id(conn, reader_id):
    return conn.execute(
        "SELECT * FROM reader_profile WHERE reader_id = ?", (reader_id,)
    ).fetchone()
