# -*- coding: utf-8 -*-
"""sqlite 连接管理。每个请求单独开连接，省得处理线程安全问题。"""
import os
import sqlite3
import threading

from src import config

_init_lock = threading.Lock()


def get_conn():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn=None):
    """建表，可重复执行（schema.sql 里都是 IF NOT EXISTS）"""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        with open(config.SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.commit()
    finally:
        if own:
            conn.close()


def ensure_ready():
    """启动时调用一次，避免并发重复建表"""
    with _init_lock:
        init_schema()
