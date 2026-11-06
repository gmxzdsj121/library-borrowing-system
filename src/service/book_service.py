# -*- coding: utf-8 -*-
"""图书与馆藏业务逻辑。迭代二新增。"""
from src.common import logger, validators
from src.dao import book_dao, user_dao
from src.db.connection import get_conn
from src.service.auth_service import AuthError


def search_books(keyword=None, category_id=None, page=1, page_size=20):
    """图书检索，所有角色都能用。"""
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    conn = get_conn()
    try:
        rows = book_dao.list_books(conn, keyword, category_id, page, page_size)
        total = book_dao.count_books(conn, keyword, category_id)
        return {
            "list": [_book_dict(r) for r in rows],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    finally:
        conn.close()


def get_book_detail(book_id):
    conn = get_conn()
    try:
        book = book_dao.get_book(conn, book_id)
        if not book:
            raise AuthError("图书不存在", 404)
        copies = book_dao.list_copies_by_book(conn, book_id)
        return {
            "book": _book_dict(book),
            "copies": [_copy_dict(c) for c in copies],
        }
    finally:
        conn.close()


def create_book(payload, operator_id):
    """馆员新增书目。"""
    conn = get_conn()
    try:
        isbn = (payload.get("isbn") or "").strip()
        title = (payload.get("title") or "").strip()
        if not title:
            raise AuthError("书名不能为空")
        if isbn:
            exists = book_dao.get_book_by_isbn(conn, isbn)
            if exists:
                raise AuthError("该 ISBN 已存在，请勿重复添加")
        book_id = book_dao.create_book(
            conn,
            isbn or None,
            title,
            (payload.get("author") or "").strip() or None,
            (payload.get("publisher") or "").strip() or None,
            payload.get("publishYear"),
            payload.get("categoryId"),
            float(payload.get("price") or 0),
        )
        user_dao.write_audit(conn, operator_id, "BOOK_CREATE", "book:%d" % book_id,
                             title, "")
        conn.commit()
        logger.info("book created id=%d title=%s" % (book_id, title))
        return {"bookId": book_id}
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("create book failed")
        raise
    finally:
        conn.close()


def add_copy(book_id, barcode, location=""):
    """给一本书新增复本（按条码）。"""
    barcode = (barcode or "").strip()
    if not barcode:
        raise AuthError("条码不能为空")
    conn = get_conn()
    try:
        book = book_dao.get_book(conn, book_id)
        if not book:
            raise AuthError("图书不存在", 404)
        old = book_dao.get_copy_by_barcode(conn, barcode)
        if old:
            raise AuthError("条码 %s 已存在" % barcode)
        copy_id = book_dao.create_copy(conn, book_id, barcode, location)
        conn.commit()
        return {"copyId": copy_id}
    except AuthError:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_categories():
    conn = get_conn()
    try:
        rows = book_dao.list_categories(conn)
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _book_dict(row):
    return {
        "bookId": row["book_id"],
        "isbn": row["isbn"] or "",
        "title": row["title"],
        "author": row["author"] or "",
        "publisher": row["publisher"] or "",
        "publishYear": row["publish_year"],
        "categoryId": row["category_id"],
        "categoryName": row["category_name"] if "category_name" in row.keys() else "",
        "price": row["price"],
        "totalCopies": row["total_copies"],
        "availableCopies": row["available_copies"],
        "status": row["status"],
    }


def _copy_dict(row):
    return {
        "copyId": row["copy_id"],
        "bookId": row["book_id"],
        "barcode": row["barcode"],
        "location": row["location"] or "",
        "status": row["status"],
    }
