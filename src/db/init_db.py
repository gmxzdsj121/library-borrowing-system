# -*- coding: utf-8 -*-
"""初始化数据库并写入演示账号。可以重复执行，已有数据不会覆盖。"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common import security  # noqa: E402
from src.dao import user_dao, book_dao, borrow_dao, reservation_dao  # noqa: E402
from src.db.connection import get_conn, init_schema  # noqa: E402


SEED_USERS = [
    # username, password, real_name, role, phone
    ("libadmin", "lib123456", "馆员-张敏", "LIBRARIAN", "13800000001"),
    ("libwang", "lib123456", "馆员-王磊", "LIBRARIAN", "13800000003"),
    ("libchen", "lib123456", "馆员-陈静", "LIBRARIAN", "13800000004"),
    ("auditor", "audit123456", "管理员-李建国", "AUDITOR", "13800000002"),
    ("reader01", "reader123456", "读者-王芳", "READER", "13900000001"),
    ("reader02", "reader123456", "读者-刘强", "READER", "13900000002"),
    ("reader03", "reader123456", "读者-赵敏", "READER", "13900000003"),
    ("reader04", "reader123456", "读者-孙伟", "READER", "13900000004"),
    ("reader05", "reader123456", "读者-周婷", "READER", "13900000005"),
    ("reader06", "reader123456", "读者-吴鹏", "READER", "13900000006"),
    ("reader07", "reader123456", "读者-郑丽", "READER", "13900000007"),
    ("reader08", "reader123456", "读者-冯超", "READER", "13900000008"),
    ("reader09", "reader123456", "读者-陈雪", "READER", "13900000009"),
    ("reader10", "reader123456", "读者-褚明", "READER", "13900000010"),
    ("reader11", "reader123456", "读者-卫华", "READER", "13900000011"),
    ("reader12", "reader123456", "读者-蒋琳", "READER", "13900000012"),
]

SEED_CATEGORIES = ["文学", "科技", "历史", "艺术", "教育", "经济", "其他"]

# 50 本图书：(isbn, title, author, publisher, publish_date, category, shelf, price, [barcodes...])
SEED_BOOKS = [
    ("9787111618637", "软件工程导论（第5版）", "张海藩", "人民邮电出版社", "2018-03-01", "科技", "A-01", 49.0, ["BC1001", "BC1002"]),
    ("9787040406641", "数据库系统概论（第5版）", "王珊", "高等教育出版社", "2014-09-01", "科技", "A-02", 43.5, ["BC2001"]),
    ("9787115428028", "Python 编程：从入门到实践", "Eric Matthes", "人民邮电出版社", "2016-07-01", "科技", "A-03", 89.0, ["BC3001", "BC3002", "BC3003"]),
    ("9787111407010", "计算机网络：自顶向下方法", "James F. Kurose", "机械工业出版社", "2014-01-01", "科技", "A-04", 79.0, ["BC4001"]),
    ("9787111213826", "数据结构（C语言版）", "严蔚敏", "清华大学出版社", "2007-03-01", "科技", "A-05", 35.0, ["BC5001", "BC5002"]),
    ("9787302423287", "算法导论（第3版）", "Thomas H. Cormen", "机械工业出版社", "2013-01-01", "科技", "A-06", 128.0, ["BC6001", "BC6002"]),
    ("9787111407011", "深入理解计算机系统", "Randal E. Bryant", "机械工业出版社", "2016-11-01", "科技", "A-07", 139.0, ["BC7001"]),
    ("9787115358790", "代码整洁之道", "Robert C. Martin", "人民邮电出版社", "2010-01-01", "科技", "A-08", 59.0, ["BC8001"]),
    ("9787111217046", "设计模式：可复用面向对象软件的基础", "Erich Gamma", "机械工业出版社", "2000-09-01", "科技", "A-09", 55.0, ["BC9001"]),
    ("9787115546098", "人工智能：一种现代的方法", "Stuart Russell", "人民邮电出版社", "2013-11-01", "科技", "A-10", 169.0, ["BC10001", "BC10002"]),
    ("9787020002207", "红楼梦", "曹雪芹", "人民文学出版社", "1996-12-01", "文学", "B-01", 59.7, ["BC11001", "BC11002", "BC11003"]),
    ("9787020008728", "三国演义", "罗贯中", "人民文学出版社", "1998-05-01", "文学", "B-02", 39.5, ["BC12001", "BC12002"]),
    ("9787020008735", "水浒传", "施耐庵", "人民文学出版社", "1997-01-01", "文学", "B-03", 40.0, ["BC13001"]),
    ("9787020008742", "西游记", "吴承恩", "人民文学出版社", "1980-05-01", "文学", "B-04", 45.0, ["BC14001", "BC14002"]),
    ("9787544253994", "百年孤独", "加西亚·马尔克斯", "南海出版公司", "2011-06-01", "文学", "B-05", 39.5, ["BC15001"]),
    ("9787020024759", "平凡的世界", "路遥", "北京十月文艺出版社", "2012-03-01", "文学", "B-06", 108.0, ["BC16001", "BC16002", "BC16003"]),
    ("9787544291170", "活着", "余华", "作家出版社", "2012-08-01", "文学", "B-07", 20.0, ["BC17001", "BC17002"]),
    ("9787544270809", "围城", "钱钟书", "人民文学出版社", "1991-02-01", "文学", "B-08", 19.0, ["BC18001"]),
    ("9787544269207", "白夜行", "东野圭吾", "南海出版公司", "2013-01-01", "文学", "B-09", 39.5, ["BC19001", "BC19002"]),
    ("9787544291163", "解忧杂货店", "东野圭吾", "南海出版公司", "2014-05-01", "文学", "B-10", 39.5, ["BC20001", "BC20002", "BC20003"]),
    ("9787101003043", "史记", "司马迁", "中华书局", "1959-09-01", "历史", "C-01", 480.0, ["BC21001"]),
    ("9787108009821", "万历十五年", "黄仁宇", "中华书局", "2007-01-01", "历史", "C-02", 36.0, ["BC22001", "BC22002"]),
    ("9787508675772", "人类简史", "尤瓦尔·赫拉利", "中信出版社", "2014-11-01", "历史", "C-03", 68.0, ["BC23001", "BC23002", "BC23003"]),
    ("9787508659706", "未来简史", "尤瓦尔·赫拉利", "中信出版社", "2017-01-01", "历史", "C-04", 68.0, ["BC24001"]),
    ("9787101131637", "中国通史", "吕思勉", "中华书局", "2015-01-01", "历史", "C-05", 48.0, ["BC25001", "BC25002"]),
    ("9787549556210", "罗马人的故事", "盐野七生", "中信出版社", "2011-01-01", "历史", "C-06", 42.0, ["BC26001"]),
    ("9787514904772", "明朝那些事儿", "当年明月", "北京联合出版公司", "2011-06-01", "历史", "C-07", 258.0, ["BC27001", "BC27002"]),
    ("9787540463440", "全球通史", "斯塔夫里阿诺斯", "北京大学出版社", "2005-01-01", "历史", "C-08", 88.0, ["BC28001"]),
    ("9787101017175", "资治通鉴", "司马光", "中华书局", "1956-06-01", "历史", "C-09", 998.0, ["BC29001"]),
    ("9787544273168", "艺术的故事", "贡布里希", "广西美术出版社", "2008-01-01", "艺术", "D-01", 280.0, ["BC30001"]),
    ("9787102047589", "中国美术史", "王伯敏", "人民美术出版社", "2000-01-01", "艺术", "D-02", 128.0, ["BC31001"]),
    ("9787549573875", "写给大家的西方美术史", "蒋勋", "湖南美术出版社", "2015-07-01", "艺术", "D-03", 68.0, ["BC32001", "BC32002"]),
    ("9787508660783", "美的历程", "李泽厚", "生活·读书·新知三联书店", "2009-01-01", "艺术", "D-04", 43.0, ["BC33001"]),
    ("9787550257405", "认识电影", "路易斯·贾内梯", "世界图书出版公司", "2016-02-01", "艺术", "D-05", 68.0, ["BC34001"]),
    ("9787549580484", "如何看懂一幅画", "弗朗索瓦芭布-高尔", "广西师范大学出版社", "2017-01-01", "艺术", "D-06", 49.0, ["BC35001"]),
    ("9787107186158", "教育学", "王道俊", "人民教育出版社", "2009-05-01", "教育", "E-01", 36.8, ["BC36001", "BC36002"]),
    ("9787504118103", "教育心理学", "陈琦", "高等教育出版社", "2011-06-01", "教育", "E-02", 48.0, ["BC37001"]),
    ("9787107179457", "给教师的建议", "苏霍姆林斯基", "教育科学出版社", "1984-06-01", "教育", "E-03", 31.0, ["BC38001", "BC38002"]),
    ("9787544432459", "第56号教室的奇迹", "雷夫·艾斯奎斯", "中国城市出版社", "2009-08-01", "教育", "E-04", 28.0, ["BC39001"]),
    ("9787501983729", "正面管教", "简·尼尔森", "京华出版社", "2009-01-01", "教育", "E-05", 35.0, ["BC40001", "BC40002"]),
    ("9787111373421", "国富论", "亚当·斯密", "商务印书馆", "2015-01-01", "经济", "F-01", 88.0, ["BC41001"]),
    ("9787508646232", "经济学原理", "曼昆", "北京大学出版社", "2015-05-01", "经济", "F-02", 128.0, ["BC42001", "BC42002"]),
    ("9787111345442", "巴菲特致股东的信", "沃伦·巴菲特", "机械工业出版社", "2007-01-01", "经济", "F-03", 38.0, ["BC43001"]),
    ("9787508633855", "思考，快与慢", "丹尼尔·卡尼曼", "中信出版社", "2012-07-01", "经济", "F-04", 69.0, ["BC44001", "BC44002"]),
    ("9787111532736", "穷查理宝典", "彼得·考夫曼", "上海人民出版社", "2010-10-01", "经济", "F-05", 88.0, ["BC45001"]),
    ("9787544257237", "牧羊少年奇幻之旅", "保罗·柯艾略", "南海出版公司", "2009-03-01", "其他", "G-01", 25.0, ["BC46001", "BC46002", "BC46003"]),
    ("9787544263216", "小王子", "圣埃克苏佩里", "人民文学出版社", "2003-08-01", "其他", "G-02", 22.0, ["BC47001", "BC47002"]),
    ("9787544245371", "追风筝的人", "卡勒德·胡赛尼", "上海人民出版社", "2006-05-01", "其他", "G-03", 29.0, ["BC48001", "BC48002"]),
    ("9787544255135", "偷影子的人", "马克·李维", "湖南文艺出版社", "2012-06-01", "其他", "G-04", 29.8, ["BC49001"]),
    ("9787544241602", "岛上书店", "加布瑞埃拉·泽文", "江苏凤凰文艺出版社", "2015-05-01", "其他", "G-05", 35.0, ["BC50001", "BC50002"]),
]


def migrate_columns(conn):
    """字段迁移：book 表 publish_year→publish_date、新增 shelf。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(book)").fetchall()}
    if "publish_year" in cols and "publish_date" not in cols:
        conn.execute("ALTER TABLE book RENAME COLUMN publish_year TO publish_date")
        print("迁移：book.publish_year → publish_date")
    if "shelf" not in cols:
        conn.execute("ALTER TABLE book ADD COLUMN shelf TEXT")
        print("迁移：book.shelf 已添加")
    # reservation 表的兼容迁移
    rcols = {r[1] for r in conn.execute("PRAGMA table_info(reservation)").fetchall()}
    if "borrow_days" not in rcols:
        conn.execute("ALTER TABLE reservation ADD COLUMN borrow_days INTEGER NOT NULL DEFAULT 30")
    if "reject_reason" not in rcols:
        conn.execute("ALTER TABLE reservation ADD COLUMN reject_reason TEXT")
    conn.commit()


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def seed_demo_data(conn):
    """注入演示数据：各种状态的借阅、罚款、预约。"""
    cnt = conn.execute("SELECT COUNT(*) AS c FROM borrow_record").fetchone()["c"]
    if cnt > 0:
        print("已有借阅记录，跳过演示数据注入")
        return

    now = datetime.now()
    readers = {}
    for row in conn.execute("SELECT u.user_id, u.username, rp.reader_id FROM sys_user u "
                            "JOIN reader_profile rp ON u.user_id = rp.user_id "
                            "WHERE u.role = 'READER'").fetchall():
        readers[row["username"]] = (row["user_id"], row["reader_id"])

    lib_user = conn.execute("SELECT user_id FROM sys_user WHERE role = 'LIBRARIAN' LIMIT 1").fetchone()
    lib_id = lib_user["user_id"] if lib_user else 1

    copies = {}
    for row in conn.execute("SELECT bc.copy_id, bc.barcode, bc.book_id, b.title FROM book_copy bc "
                            "JOIN book b ON bc.book_id = b.book_id").fetchall():
        copies[row["barcode"]] = (row["copy_id"], row["book_id"], row["title"])

    def _borrow(reader_key, barcode, days_ago, due_days, status='BORROWED'):
        uid, rid = readers[reader_key]
        copy_id, book_id, title = copies[barcode]
        borrow_at = now - timedelta(days=days_ago)
        due_at = borrow_at + timedelta(days=due_days)
        rec_id = conn.execute(
            """INSERT INTO borrow_record (reader_id, copy_id, borrow_at, due_at, renew_count, status, operator_id, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?, ?)""",
            (rid, copy_id, _fmt(borrow_at), _fmt(due_at), status, lib_id, _fmt(borrow_at))
        ).lastrowid
        if status in ('BORROWED', 'OVERDUE'):
            conn.execute("UPDATE book_copy SET status = 'BORROWED' WHERE copy_id = ?", (copy_id,))
            conn.execute("UPDATE book SET available_copies = available_copies - 1 WHERE book_id = ?", (book_id,))
        else:
            conn.execute("UPDATE book_copy SET status = 'AVAILABLE' WHERE copy_id = ?", (copy_id,))
        return rec_id, rid, due_at

    # 正常借阅中（7条）
    normal_borrows = [
        ("reader01", "BC1001", 10, 30),
        ("reader02", "BC11001", 5, 30),
        ("reader03", "BC15001", 15, 30),
        ("reader04", "BC23001", 3, 30),
        ("reader05", "BC36001", 20, 30),
        ("reader06", "BC42001", 8, 30),
        ("reader07", "BC46001", 12, 30),
    ]
    for rk, bc, da, dd in normal_borrows:
        _borrow(rk, bc, days_ago=da, due_days=dd, status='BORROWED')

    # 逾期未还（8条，含部分已缴罚款）
    overdue_borrows = [
        ("reader01", "BC2001", 40, 30),
        ("reader02", "BC3001", 35, 30),
        ("reader03", "BC4001", 50, 30),
        ("reader04", "BC12001", 45, 30),
        ("reader05", "BC14001", 38, 30),
        ("reader06", "BC16001", 42, 30),
        ("reader07", "BC19001", 55, 30),
        ("reader08", "BC21001", 48, 30),
    ]
    for i, (rk, bc, da, dd) in enumerate(overdue_borrows):
        rec_id, rid, due_at = _borrow(rk, bc, days_ago=da, due_days=dd, status='OVERDUE')
        overdue_days = da - dd - 3  # FINE_FREE_DAYS=3
        fine_amount = round(max(0, overdue_days) * 0.5, 2)
        fine_status = 'PAID' if i < 3 else 'UNPAID'
        conn.execute(
            """INSERT INTO fine_record (record_id, reader_id, overdue_days, amount, status, created_at, paid_at, operator_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rec_id, rid, max(0, overdue_days), fine_amount, fine_status,
             _fmt(now), _fmt(now) if fine_status == 'PAID' else None,
             lib_id if fine_status == 'PAID' else None)
        )

    # 已归还（8条）
    returned_borrows = [
        ("reader08", "BC1002", 60, 30),
        ("reader09", "BC11002", 55, 30),
        ("reader10", "BC12002", 40, 30),
        ("reader11", "BC13001", 35, 30),
        ("reader12", "BC14002", 25, 30),
        ("reader01", "BC17001", 50, 30),
        ("reader02", "BC22001", 30, 30),
        ("reader03", "BC24001", 45, 30),
    ]
    for rk, bc, da, dd in returned_borrows:
        rec_id, rid, due_at = _borrow(rk, bc, days_ago=da, due_days=dd, status='RETURNED')
        conn.execute("UPDATE borrow_record SET return_at = ? WHERE record_id = ?",
                     (_fmt(now - timedelta(days=5)), rec_id))

    # 待审批预约（1条）
    ds_book = conn.execute("SELECT book_id FROM book WHERE title LIKE '%数据结构%'").fetchone()
    if ds_book and "reader01" in readers:
        uid01, rid01 = readers["reader01"]
        q = conn.execute("SELECT COALESCE(MAX(queue_no),0)+1 AS m FROM reservation WHERE book_id = ?",
                         (ds_book["book_id"],)).fetchone()["m"]
        conn.execute(
            """INSERT INTO reservation (reader_id, book_id, queue_no, borrow_days, status, created_at)
               VALUES (?, ?, ?, 30, 'PENDING', ?)""",
            (rid01, ds_book["book_id"], q, _fmt(now))
        )

    conn.commit()
    print("演示数据已注入：7条借阅中、8条逾期（3条已缴罚款）、8条已归还、1条待审批预约")


def seed():
    init_schema()
    conn = get_conn()
    try:
        migrate_columns(conn)

        exists = conn.execute("SELECT COUNT(*) AS c FROM sys_user").fetchone()["c"]
        if not exists:
            for username, pwd, real_name, role, phone in SEED_USERS:
                uid = user_dao.create_user(conn, username, security.make_password(pwd),
                                           real_name, phone, role)
                if role == "READER":
                    user_dao.create_reader_profile(conn, uid, username, "ADULT")
                print("创建账号：%s / %s（%s）" % (username, pwd, role))
            conn.commit()
        else:
            print("已有 %d 个账号，跳过账号初始化" % exists)

        # 分类种子
        cat_count = conn.execute("SELECT COUNT(*) AS c FROM book_category").fetchone()["c"]
        if cat_count == 0:
            for i, name in enumerate(SEED_CATEGORIES):
                book_dao.create_category(conn, name, sort_no=i)
            conn.commit()
            print("已创建 %d 个图书分类" % len(SEED_CATEGORIES))

        # 图书种子
        book_count = conn.execute("SELECT COUNT(*) AS c FROM book").fetchone()["c"]
        if book_count == 0:
            cats = {r["name"]: r["category_id"]
                    for r in conn.execute("SELECT * FROM book_category").fetchall()}
            for isbn, title, author, pub, pdate, cat_name, shelf, price, codes in SEED_BOOKS:
                bid = book_dao.create_book(conn, isbn, title, author, pub, pdate,
                                           cats.get(cat_name), shelf, price)
                for code in codes:
                    book_dao.create_copy(conn, bid, code, shelf)
            conn.commit()
            print("导入图书：%d 种" % len(SEED_BOOKS))
        else:
            print("已有 %d 条书目，跳过图书种子" % book_count)

        seed_demo_data(conn)

        print("数据库初始化完成：", os.path.abspath(__import__("src.config", fromlist=["DB_PATH"]).DB_PATH))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
