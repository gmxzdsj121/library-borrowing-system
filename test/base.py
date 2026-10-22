# -*- coding: utf-8 -*-
"""测试公共准备：每个用例用一个临时数据库，跑完就删。"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import config  # noqa: E402
from src.db import connection  # noqa: E402


class DbTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        config.DB_PATH = self.db_path
        connection.init_schema()

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except OSError:
            pass
