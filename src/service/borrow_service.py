# -*- coding: utf-8 -*-
"""借阅 / 归还 / 续借 / 罚款 业务逻辑。迭代二核心。"""
from datetime import datetime, timedelta

from src import config
from src.common import logger
from src.dao import book_dao, borrow_dao, reservation_dao, user_dao
from src.db.connection import get_conn
from src.service.auth_service import AuthError

MAX_RENEW = 2  # 单条借阅最多续借 2 次


def _reader_of(conn, user_id):
    rp = book_dao.get_reader_profile(conn, user_id)
    if not rp:
        raise AuthError("该账号没有读者档案", 403)
    return rp


def borrow_book(reader_user_id, copy_barcode, operator_id):
    """馆员办理借书：读者资格校验 + 复本可借校验，写入借阅记录。"""
    conn = get_conn()
    try:
        rp = _reader_of(conn, reader_user_id)
        reader_id = rp["reader_id"]

        # 资格 1：在借数量不超限
        active = borrow_dao.count_active_borrows(conn, reader_id)
        if active >= rp["max_borrow"]:
            raise AuthError("在借数量已达上限（%d 册）" % rp["max_borrow"])
        # 资格 2：没有逾期未还
        if borrow_dao.has_overdue(conn, reader_id):
            raise AuthError("您有逾期未还的图书，请先归还")
        # 资格 3：没有未结清罚款
        if borrow_dao.has_unpaid_fine(conn, reader_id):
            raise AuthError("您有未结清的罚款，请先缴纳")
        # 资格 4：信用分
        if rp["credit_score"] < 60:
            raise AuthError("信用分过低，无法借书")

        copy = book_dao.get_copy_by_barcode(conn, copy_barcode)
        if not copy:
            raise AuthError("条码不存在")
        if copy["status"] != "AVAILABLE":
            raise AuthError("该复本当前不可借（状态：%s）" % copy["status"])

        book_id = copy["book_id"]
        # 应还日期 = 今天 + BORROW_DAYS 天
        due_at = (datetime.now() + timedelta(days=config.BORROW_DAYS)).strftime(
            "%Y-%m-%d %H:%M:%S")

        record_id = borrow_dao.create_borrow(conn, reader_id, copy["copy_id"],
                                             due_at, operator_id)
        book_dao.set_copy_status(conn, copy["copy_id"], "BORROWED")
        book_dao.adjust_available(conn, book_id, -1)

        user_dao.write_audit(conn, operator_id, "BORROW",
                             "record:%d" % record_id,
                             "reader=%d copy=%s" % (reader_id, copy_barcode), "")
        conn.commit()
        logger.info("borrow ok record=%d reader=%d copy=%s"
                    % (record_id, reader_id, copy_barcode))
        return {"recordId": record_id, "dueAt": due_at}
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("borrow failed")
        raise
    finally:
        conn.close()


def return_book(copy_barcode, operator_id):
    """归还：算逾期天数、生成罚款单、回置复本状态、触发预约到书通知。"""
    conn = get_conn()
    try:
        copy = book_dao.get_copy_by_barcode(conn, copy_barcode)
        if not copy:
            raise AuthError("条码不存在")
        # 找到这条复本当前活跃的借阅记录
        row = conn.execute(
            "SELECT * FROM borrow_record WHERE copy_id = ? AND status != 'RETURNED' "
            "ORDER BY borrow_at DESC LIMIT 1",
            (copy["copy_id"],),
        ).fetchone()
        if not row:
            raise AuthError("该复本没有在借记录")

        record_id = row["record_id"]
        overdue_days = borrow_dao.compute_overdue_days(row["due_at"])
        fine_id = None
        amount = 0
        if overdue_days > 0:
            amount = borrow_dao.compute_fine_amount(overdue_days)
            fine_id = borrow_dao.create_fine(conn, record_id, row["reader_id"],
                                             overdue_days, amount)
            # 逾期自动降信用分，每次扣 2 分
            conn.execute(
                "UPDATE reader_profile SET credit_score = credit_score - 2 "
                "WHERE reader_id = ?",
                (row["reader_id"],),
            )

        borrow_dao.return_borrow(conn, record_id)
        book_dao.set_copy_status(conn, copy["copy_id"], "AVAILABLE")
        book_dao.adjust_available(conn, copy["book_id"], 1)

        # 如果有人预约这本书，通知队首读者到书，保留 3 天
        head = reservation_dao.get_head_reservation(conn, copy["book_id"])
        if head:
            reservation_dao.ready_reservation(conn, head["reservation_id"])

        user_dao.write_audit(conn, operator_id, "RETURN",
                             "record:%d" % record_id,
                             "overdue_days=%d fine=%.2f" % (overdue_days, amount), "")
        conn.commit()
        return {
            "recordId": record_id,
            "overdueDays": overdue_days,
            "fineId": fine_id,
            "fineAmount": amount,
        }
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("return failed")
        raise
    finally:
        conn.close()


def renew_book(reader_user_id, record_id):
    """读者自助续借：最多 2 次，已逾期或被预约时禁止。"""
    conn = get_conn()
    try:
        rp = _reader_of(conn, reader_user_id)
        record = borrow_dao.get_borrow(conn, record_id)
        if not record or record["reader_id"] != rp["reader_id"]:
            raise AuthError("借阅记录不存在", 404)
        if record["status"] == "RETURNED":
            raise AuthError("该借阅记录已归还")
        if record["status"] == "OVERDUE":
            raise AuthError("已逾期，无法续借")
        if record["renew_count"] >= MAX_RENEW:
            raise AuthError("已达到最大续借次数（%d 次）" % MAX_RENEW)
        # 该书被他人预约则不可续借
        if reservation_dao.has_queuing_reservation(conn, rp["reader_id"],
                                                   _book_id_of(conn, record["copy_id"])):
            # 注意：has_queuing_reservation 第一个参数是 reader_id，
            # 我们要查的是"有没有别人预约"，所以传 -1 表示不限读者
            queuers = reservation_dao.get_queuing_by_book(
                conn, _book_id_of(conn, record["copy_id"]))
            if queuers:
                raise AuthError("该书已被预约，无法续借")

        new_due = (datetime.strptime(record["due_at"], "%Y-%m-%d %H:%M:%S")
                   + timedelta(days=config.BORROW_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        borrow_dao.renew_borrow(conn, record_id, new_due)
        user_dao.write_audit(conn, rp["user_id"], "RENEW",
                             "record:%d" % record_id,
                             "renew_count=%d" % (record["renew_count"] + 1), "")
        conn.commit()
        return {"recordId": record_id, "newDueAt": new_due}
    except AuthError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        logger.warn("renew failed")
        raise
    finally:
        conn.close()


def _book_id_of(conn, copy_id):
    return book_dao.get_copy(conn, copy_id)["book_id"]


def list_my_borrows(reader_user_id):
    conn = get_conn()
    try:
        rp = _reader_of(conn, reader_user_id)
        rows = borrow_dao.get_borrows_by_reader(conn, rp["reader_id"])
        return [_borrow_dict(r) for r in rows]
    finally:
        conn.close()


def pay_fine(fine_id, operator_id):
    conn = get_conn()
    try:
        fine = borrow_dao.get_fine(conn, fine_id)
        if not fine:
            raise AuthError("罚款记录不存在", 404)
        if fine["status"] != "UNPAID":
            raise AuthError("该罚款已处理")
        borrow_dao.pay_fine(conn, fine_id, operator_id)
        user_dao.write_audit(conn, operator_id, "FINE_PAY",
                             "fine:%d" % fine_id, "amount=%.2f" % fine["amount"], "")
        conn.commit()
        return {"fineId": fine_id, "status": "PAID"}
    except AuthError:
        conn.rollback()
        raise
    finally:
        conn.close()


def waive_fine(fine_id, operator_id):
    """审核统计管理员减免罚款。"""
    conn = get_conn()
    try:
        fine = borrow_dao.get_fine(conn, fine_id)
        if not fine:
            raise AuthError("罚款记录不存在", 404)
        if fine["status"] != "UNPAID":
            raise AuthError("该罚款已处理")
        borrow_dao.waive_fine(conn, fine_id, operator_id)
        user_dao.write_audit(conn, operator_id, "FINE_WAIVE",
                             "fine:%d" % fine_id, "", "")
        conn.commit()
        return {"fineId": fine_id, "status": "WAIVED"}
    except AuthError:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_fines(reader_user_id=None, status=None):
    conn = get_conn()
    try:
        if reader_user_id:
            rp = _reader_of(conn, reader_user_id)
            rows = borrow_dao.list_fines_by_reader(conn, rp["reader_id"], status)
        else:
            sql = "SELECT * FROM fine_record WHERE 1=1"
            args = []
            if status:
                sql += " AND status = ?"
                args.append(status)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _borrow_dict(row):
    return {
        "recordId": row["record_id"],
        "readerId": row["reader_id"],
        "copyId": row["copy_id"],
        "borrowAt": row["borrow_at"],
        "dueAt": row["due_at"],
        "returnAt": row["return_at"],
        "renewCount": row["renew_count"],
        "status": row["status"],
    }
