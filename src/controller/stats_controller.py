# -*- coding: utf-8 -*-
"""统计报表接口控制器（FR-12）。"""
from src.service import stats_service


def handle_overview():
    return {"code": 0, "msg": "ok", "data": stats_service.overview()}


def handle_trend(query):
    days = int(query.get("days", 30))
    return {"code": 0, "msg": "ok", "data": stats_service.borrow_trend(days)}


def handle_popular(query):
    top = int(query.get("top", 10))
    return {"code": 0, "msg": "ok", "data": stats_service.popular_books(top)}


def handle_fine_summary():
    return {"code": 0, "msg": "ok", "data": stats_service.fine_summary()}
