# -*- coding: utf-8 -*-
"""统计报表与通知公告模块测试（FR-12、FR-13）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from base import DbTestCase  # noqa: E402
from src.service import stats_service, notice_service, book_service  # noqa: E402
from src.dao import user_dao  # noqa: E402
from src.common import security  # noqa: E402
from src.db.connection import get_conn  # noqa: E402


class StatsOverviewTest(DbTestCase):
    def test_overview_counts(self):
        conn = get_conn()
        lib = user_dao.create_user(conn, "lib1", security.make_password("lib123456"),
                                   "馆员", "", "LIBRARIAN")
        conn.commit()
        conn.close()
        book_id = book_service.create_book(
            {"isbn": "S1", "title": "统计书", "price": 40}, lib)["bookId"]
        book_service.add_copy(book_id, "SC001")

        ov = stats_service.overview()
        self.assertEqual(ov["bookTotal"], 1)
        self.assertEqual(ov["copyTotal"], 1)
        self.assertEqual(ov["available"], 1)
        self.assertEqual(ov["borrowed"], 0)


class StatsTrendTest(DbTestCase):
    def test_trend_has_dates(self):
        trend = stats_service.borrow_trend(days=7)
        self.assertEqual(len(trend), 7)
        for item in trend:
            self.assertIn("date", item)
            self.assertIn("borrow", item)
            self.assertIn("return", item)


class FineSummaryTest(DbTestCase):
    def test_summary_zero_when_empty(self):
        fs = stats_service.fine_summary()
        self.assertEqual(fs["total"], 0.0)
        self.assertEqual(fs["paid"], 0.0)


class NoticeTest(DbTestCase):
    def test_publish_and_list(self):
        conn = get_conn()
        lib = user_dao.create_user(conn, "lib2", security.make_password("lib123456"),
                                   "馆员", "", "LIBRARIAN")
        conn.commit()
        conn.close()
        notice_service.create_notice("系统升级公告", "本周六凌晨维护", lib)
        notices = notice_service.list_notices(lib)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["title"], "系统升级公告")

    def test_mark_read(self):
        conn = get_conn()
        lib = user_dao.create_user(conn, "lib3", security.make_password("lib123456"),
                                   "馆员", "", "LIBRARIAN")
        conn.commit()
        conn.close()
        notice_service.create_notice("测试", "内容", lib)
        nid = notice_service.list_notices(lib)[0]["id"]
        notice_service.mark_read(nid, lib)
        self.assertEqual(notice_service.list_notices(lib)[0]["isRead"], 1)

    def test_ready_notice(self):
        conn = get_conn()
        reader = user_dao.create_user(conn, "r1", security.make_password("r1234567"),
                                      "读者", "", "READER")
        user_dao.create_reader_profile(conn, reader, "r1", "STUDENT")
        conn.commit()
        conn.close()
        notice_service.push_ready_notice(reader, "Python编程")
        notices = notice_service.list_notices(reader)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0]["type"], "RESERVE")


if __name__ == "__main__":
    import unittest
    unittest.main()
