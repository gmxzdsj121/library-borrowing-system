-- ============================================================
--  图书借阅管理系统 基础数据结构（迭代一）
--  说明：本文件只建"表"，借阅/预约/罚款等业务规则在迭代二实现
--  数据库：SQLite 3.x    字符集：UTF-8
-- ============================================================

PRAGMA foreign_keys = ON;

-- 1. 用户账号表（读者、馆员、审核统计管理员共用一张表，用 role 区分）
CREATE TABLE IF NOT EXISTS sys_user (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL,                       -- 登录名（读者为读者证号）
    password_hash TEXT    NOT NULL,                       -- PBKDF2-SHA256 加盐散列串
    real_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'READER'
                  CHECK (role IN ('READER','LIBRARIAN','AUDITOR')),
    status        TEXT    NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE','FROZEN','PENDING')),
    phone         TEXT,
    fail_count    INTEGER NOT NULL DEFAULT 0,             -- 连续登录失败次数
    lock_until    TEXT,                                   -- 锁定截止时间
    last_login_at TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_user_username ON sys_user(username);
CREATE INDEX IF NOT EXISTS idx_user_role ON sys_user(role);

-- 2. 读者档案表（只有 role=READER 的账号才有对应档案）
CREATE TABLE IF NOT EXISTS reader_profile (
    reader_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL UNIQUE,
    reader_no    TEXT    NOT NULL,
    reader_type  TEXT    NOT NULL DEFAULT 'STUDENT'
                 CHECK (reader_type IN ('STUDENT','TEACHER')),
    max_borrow   INTEGER NOT NULL DEFAULT 5,             -- 可借上限
    credit_score INTEGER NOT NULL DEFAULT 100,           -- 信用分，欠费/逾期扣分
    created_at   TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_reader_no ON reader_profile(reader_no);

-- 3. 会话表（登录成功后签发令牌，30 分钟不活跃失效）
CREATE TABLE IF NOT EXISTS sys_session (
    token      TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT    NOT NULL,
    expire_at  TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_session_user ON sys_session(user_id);

-- 4. 业务操作日志表（课程底线要求：关键操作留痕）
CREATE TABLE IF NOT EXISTS sys_audit_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    action     TEXT    NOT NULL,                          -- REGISTER/LOGIN/LOGIN_FAIL/LOGOUT...
    target     TEXT,
    detail     TEXT,
    ip         TEXT,
    result     TEXT    NOT NULL DEFAULT 'OK',
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON sys_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON sys_audit_log(created_at);

-- 5. 图书分类表
CREATE TABLE IF NOT EXISTS book_category (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    parent_id   INTEGER,
    sort_no     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (parent_id) REFERENCES book_category(category_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_category_name ON book_category(name);

-- 6. 书目表（一种书一条记录，复本信息放 book_copy）
CREATE TABLE IF NOT EXISTS book (
    book_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn             TEXT,
    title            TEXT    NOT NULL,
    author           TEXT,
    publisher        TEXT,
    publish_year     INTEGER,
    category_id      INTEGER,
    price            REAL    NOT NULL DEFAULT 0,
    total_copies     INTEGER NOT NULL DEFAULT 0,
    available_copies INTEGER NOT NULL DEFAULT 0,
    status           TEXT    NOT NULL DEFAULT 'ON_SHELF'
                     CHECK (status IN ('ON_SHELF','OFF_SHELF')),
    created_at       TEXT    NOT NULL,
    FOREIGN KEY (category_id) REFERENCES book_category(category_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_book_isbn ON book(isbn);
CREATE INDEX IF NOT EXISTS idx_book_title ON book(title);

-- 7. 馆藏复本表（每本实体书一条，条码唯一，状态随借还流转）
CREATE TABLE IF NOT EXISTS book_copy (
    copy_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id    INTEGER NOT NULL,
    barcode    TEXT    NOT NULL,
    location   TEXT,
    status     TEXT    NOT NULL DEFAULT 'AVAILABLE'
               CHECK (status IN ('AVAILABLE','BORROWED','RESERVED','LOST','REPAIR')),
    created_at TEXT    NOT NULL,
    FOREIGN KEY (book_id) REFERENCES book(book_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_copy_barcode ON book_copy(barcode);

-- 8. 借阅记录表（状态：BORROWED 借出中 / OVERDUE 逾期 / RETURNED 已归还）
CREATE TABLE IF NOT EXISTS borrow_record (
    record_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    reader_id   INTEGER NOT NULL,
    copy_id     INTEGER NOT NULL,
    borrow_at   TEXT    NOT NULL,
    due_at      TEXT    NOT NULL,
    return_at   TEXT,
    renew_count INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'BORROWED'
                CHECK (status IN ('BORROWED','OVERDUE','RETURNED')),
    operator_id INTEGER,
    created_at  TEXT    NOT NULL,
    FOREIGN KEY (reader_id) REFERENCES reader_profile(reader_id),
    FOREIGN KEY (copy_id) REFERENCES book_copy(copy_id),
    FOREIGN KEY (operator_id) REFERENCES sys_user(user_id)
);
CREATE INDEX IF NOT EXISTS idx_borrow_reader ON borrow_record(reader_id, status);
CREATE INDEX IF NOT EXISTS idx_borrow_copy ON borrow_record(copy_id, status);

-- 9. 预约表（队列号唯一，到书后保留 3 天）
CREATE TABLE IF NOT EXISTS reservation (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    reader_id      INTEGER NOT NULL,
    book_id        INTEGER NOT NULL,
    queue_no       INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'QUEUING'
                   CHECK (status IN ('QUEUING','READY','FULFILLED','EXPIRED','CANCELLED')),
    created_at     TEXT    NOT NULL,
    ready_at       TEXT,
    expire_at      TEXT,
    fulfilled_at   TEXT,
    FOREIGN KEY (reader_id) REFERENCES reader_profile(reader_id),
    FOREIGN KEY (book_id) REFERENCES book(book_id)
);
CREATE INDEX IF NOT EXISTS idx_resv_book ON reservation(book_id, status);

-- 10. 罚款表（按借阅记录生成，可减免，减免需审核统计管理员审批）
CREATE TABLE IF NOT EXISTS fine_record (
    fine_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id   INTEGER NOT NULL,
    reader_id   INTEGER NOT NULL,
    overdue_days INTEGER NOT NULL DEFAULT 0,
    amount      REAL    NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'UNPAID'
                CHECK (status IN ('UNPAID','PAID','WAIVED')),
    created_at  TEXT    NOT NULL,
    paid_at     TEXT,
    operator_id INTEGER,
    FOREIGN KEY (record_id) REFERENCES borrow_record(record_id),
    FOREIGN KEY (reader_id) REFERENCES reader_profile(reader_id)
);
CREATE INDEX IF NOT EXISTS idx_fine_reader ON fine_record(reader_id, status);

-- 11. 通知/公告表（到期提醒、预约到书通知、管理员公告）
CREATE TABLE IF NOT EXISTS notice (
    notice_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    title      TEXT    NOT NULL,
    content    TEXT,
    type       TEXT    NOT NULL DEFAULT 'SYSTEM'
               CHECK (type IN ('SYSTEM','DUE','RESERVE','ANNOUNCE')),
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notice_user ON notice(user_id, is_read);
