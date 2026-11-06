# -*- coding: utf-8 -*-
"""迭代二：核心业务流程的少量冒烟测试（完整测试留到迭代三）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from base import DbTestCase  # noqa: E402
from src.common import security  # noqa: E402
from src.dao import user_dao, book_dao  # noqa: E402
from src.db.connection import get_conn  # noqa: E402
from src.service import book_service, borrow_service, reservation_service, auth_service  # noqa: E402


def _seed():
    conn = get_conn()
    admin = user_dao.create_user(conn, "libadmin", security.make_password("lib123456"),
                                 "馆员", "", "LIBRARIAN")
    reader = user_dao.create_user(conn, "reader01", security.make_password("reader123456"),
                                  "读者", "", "READER")
    user_dao.create_reader_profile(conn, reader, "reader01", "STUDENT")
    conn.commit()
    conn.close()
    return admin, reader


class BorrowFlowTest(DbTestCase):
    def test_borrow_and_return(self):
        admin_id, reader_id = _seed()
        book_id = book_service.create_book({"isbn": "I1", "title": "测试书", "price": 30}, admin_id)["bookId"]
        book_service.add_copy(book_id, "BC001")

        # 借书
        b = borrow_service.borrow_book(reader_id, "BC001", admin_id)
        self.assertIn("recordId", b)
        self.assertEqual(book_service.get_book_detail(book_id)["book"]["availableCopies"], 0)

        # 不逾期归还
        ret = borrow_service.return_book("BC001", admin_id)
        self.assertEqual(ret["overdueDays"], 0)
        self.assertIsNone(ret["fineId"])
        self.assertEqual(book_service.get_book_detail(book_id)["book"]["availableCopies"], 1)

    def test_overdue_fine(self):
        admin_id, reader_id = _seed()
        book_id = book_service.create_book({"isbn": "I2", "title": "测试书2", "price": 30}, admin_id)["bookId"]
        book_service.add_copy(book_id, "BC002")
        b = borrow_service.borrow_book(reader_id, "BC002", admin_id)

        conn = get_conn()
        conn.execute("UPDATE borrow_record SET due_at = ? WHERE record_id = ?",
                     ("2020-01-01 00:00:00", b["recordId"]))
        conn.commit()
        conn.close()

        ret = borrow_service.return_book("BC002", admin_id)
        self.assertGreater(ret["overdueDays"], 0)
        self.assertGreater(ret["fineAmount"], 0)

        fines = borrow_service.list_fines(reader_id)
        self.assertEqual(fines[0]["status"], "UNPAID")
        borrow_service.pay_fine(fines[0]["fine_id"], admin_id)
        self.assertEqual(borrow_service.list_fines(reader_id)[0]["status"], "PAID")


class ReserveTest(DbTestCase):
    def test_reserve_when_no_available(self):
        _admin_id, reader_id = _seed()
        book_id = book_service.create_book({"isbn": "I3", "title": "测试书3", "price": 30}, 1)["bookId"]
        # 没有复本，available=0，可以预约
        res = reservation_service.reserve_book(reader_id, book_id)
        self.assertEqual(res["queueNo"], 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
