# -*- coding: utf-8 -*-
"""业务操作日志：文件里写一份，数据库里也留一份，方便审计统计管理员查。"""
import logging
import os

from src import config

_ready = False


def _logger():
    global _ready
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log = logging.getLogger("library.business")
    if not _ready:
        log.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh = logging.FileHandler(os.path.join(config.LOG_DIR, "business.log"), encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        log.addHandler(sh)
        _ready = True
    return log


def info(msg):
    _logger().info(msg)


def warn(msg):
    _logger().warning(msg)
