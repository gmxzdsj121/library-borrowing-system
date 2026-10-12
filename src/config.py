# -*- coding: utf-8 -*-
"""全局配置。数据库路径允许用环境变量覆盖，方便跑单元测试。"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")

DB_PATH = os.environ.get("LIBRARY_DB") or os.path.join(DATA_DIR, "library.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "src", "db", "schema.sql")

# --- 登录安全相关 ---
SESSION_MINUTES = 30          # 会话有效期（分钟）
LOGIN_FAIL_LIMIT = 5          # 连续失败几次锁定
LOCK_MINUTES = 15             # 锁定时长
PBKDF2_ROUNDS = 120000        # 迭代次数，实验室机器上大约 60ms 一次

# --- 业务规则（迭代二启用，这里先集中放好，免得后面到处找）---
BORROW_DAYS = 30              # 借期 30 天
MAX_BORROW = 5                # 同时在借上限
FINE_PER_DAY = 0.5            # 每天罚金（元）
FINE_FREE_DAYS = 3            # 宽限期
RESERVE_KEEP_DAYS = 3         # 预约到书保留天数

# 10-22 试过把 LOCK_MINUTES 改成 5，测试的时候锁了两次就登不进去，还是 15 分钟合适
