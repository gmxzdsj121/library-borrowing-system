# -*- coding: utf-8 -*-
"""图书相关接口的控制器。"""
from src.service import book_service


def handle_search(query, user):
    keyword = query.get("keyword")
    category_id = query.get("categoryId")
    page = int(query.get("page", 1))
    page_size = int(query.get("pageSize", 20))
    data = book_service.search_books(keyword, category_id, page, page_size)
    return {"code": 0, "msg": "ok", "data": data}


def handle_detail(book_id):
    data = book_service.get_book_detail(int(book_id))
    return {"code": 0, "msg": "ok", "data": data}


def handle_create(payload, user):
    data = book_service.create_book(payload, user["userId"])
    return {"code": 0, "msg": "新增成功", "data": data}


def handle_add_copy(payload, user):
    data = book_service.add_copy(
        int(payload["bookId"]), payload["barcode"], payload.get("location", ""))
    return {"code": 0, "msg": "复本已添加", "data": data}


def handle_categories():
    data = book_service.list_categories()
    return {"code": 0, "msg": "ok", "data": data}
