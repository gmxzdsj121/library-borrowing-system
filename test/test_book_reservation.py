# -*- coding: utf-8 -*-
"""图书管理与预约服务测试（FR-03、FR-04、FR-05、FR-09）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from base import DbTestCase  # noqa: E402
from src.service import book_service, reservation_service  # noqa: E402
from src.dao import user_dao  # noqa: E402
from src.common import security  # noqa: E402
from src.db.connection import get_conn  # noqa: E402


def _seed_admin():
    conn = get_conn()
    lib = user_dao.create_user(conn, "libb", security.make_password("lib123456"),
                               "馆员", "", "LIBRARIAN")
    conn.commit()
    conn.close()
    return lib


class BookServiceTest(DbTestCase):
    def test_create_and_search(self):
        lib = _seed_admin()
        bid = book_service.create_book(
            {"isbn": "B1", "title": "Python入门", "author": "张三",
             "publisher": "清华大学出版社", "price": 59.0}, lib)["bookId"]
        result = book_service.search_books("Python")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["list"][0]["bookId"], bid)

    def test_search_by_author(self):
        lib = _seed_admin()
        book_service.create_book(
            {"isbn": "B2", "title": "Java核心", "author": "李四", "price": 88}, lib)
        result = book_service.search_books("李四")
        self.assertEqual(result["total"], 1)

    def test_add_copy_updates_available(self):
        lib = _seed_admin()
        bid = book_service.create_book(
            {"isbn": "B3", "title": "算法导论", "price": 128}, lib)["bookId"]
        book_service.add_copy(bid, "C001")
        book_service.add_copy(bid, "C002")
        detail = book_service.get_book_detail(bid)
        self.assertEqual(detail["book"]["totalCopies"], 2)
        self.assertEqual(detail["book"]["availableCopies"], 2)

    def test_categories_list(self):
        cats = book_service.list_categories()
        self.assertIsInstance(cats, list)


class ReservationServiceTest(DbTestCase):
    def test_reserve_queue_position(self):
        conn = get_conn()
        reader1 = user_dao.create_user(conn, "rr1", security.make_password("r1234567"),
                                       "读者1", "", "READER")
        reader2 = user_dao.create_user(conn, "rr2", security.make_password("r2345678"),
                                       "读者2", "", "READER")
        user_dao.create_reader_profile(conn, reader1, "rr1", "STUDENT")
        user_dao.create_reader_profile(conn, reader2, "rr2", "STUDENT")
        conn.commit()
        conn.close()
        lib = _seed_admin()
        bid = book_service.create_book(
            {"isbn": "B4", "title": "预约测试书", "price": 30}, lib)["bookId"]

        r1 = reservation_service.reserve_book(reader1, bid)
        r2 = reservation_service.reserve_book(reader2, bid)
        self.assertEqual(r1["queueNo"], 1)
        self.assertEqual(r2["queueNo"], 2)

    def test_cancel_reservation(self):
        conn = get_conn()
        reader = user_dao.create_user(conn, "rr3", security.make_password("r1234567"),
                                      "读者3", "", "READER")
        user_dao.create_reader_profile(conn, reader, "rr3", "STUDENT")
        conn.commit()
        conn.close()
        lib = _seed_admin()
        bid = book_service.create_book(
            {"isbn": "B5", "title": "取消预约书", "price": 30}, lib)["bookId"]
        res = reservation_service.reserve_book(reader, bid)
        reservation_service.cancel_reservation(reader, res["reservationId"])
        my = reservation_service.list_my_reservations(reader)
        self.assertEqual(len(my), 1)
        self.assertEqual(my[0]["status"], "CANCELLED")


if __name__ == "__main__":
    import unittest
    unittest.main()
