#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""退款数据共用: 解析 / 状态映射 / 派生写入器。只读平台, 直连 db_spzx。"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pnl_common import PLATFORM_TAOBAO, connect_db, log, parse_dt, parse_money  # noqa: E402,F401

DERIVED_CODE = "auto-refund"


def build_refund_row(f, shop_id):
    """JS 抽出的原始字符串字段 → refund_order 行 dict; 无退款编号返回 None。"""
    refund_no = (f.get("refund_no") or "").strip()
    if not refund_no:
        return None
    return {
        "platform_type": PLATFORM_TAOBAO,
        "shop_id": shop_id if shop_id is not None else 0,
        "refund_no": refund_no,
        "order_no": (f.get("order_no") or "").strip() or None,
        "after_sale_type": f.get("after_sale_type") or None,
        "status": f.get("status") or None,
        "refund_amount": parse_money(f.get("refund_amount")),
        "order_amount": parse_money(f.get("order_amount")),
        "apply_time": parse_dt(f.get("apply_time")),
        "finish_time": parse_dt(f.get("finish_time")),
        "reason": f.get("reason") or None,
        "product_title": f.get("product_title") or None,
        "sku_name": f.get("sku_name") or None,
        "item_id": (f.get("item_id") or "").strip() or None,
        "buyer_nick": f.get("buyer_nick") or None,
        "raw_json": f.get("raw"),
    }


def map_import_order_status(order_status):
    """order_info.order_status(int) → refund_import_order.order_status(str)。

    口径对齐 pnl_common.TRADE_STATUS_MAP / MallRefundRecordServiceImpl 常量:
    1=买家已付款(等待卖家发货)、2=卖家已发货、0=待付款(等待买家付款)。
    字符串必须与 MallRefundRecordServiceImpl 的 ORDER_STATUS_* 逐字一致。
    """
    return {3: "交易成功", -1: "交易关闭",
            1: "买家已付款,等待卖家发货",
            2: "卖家已发货，等待买家确认",
            0: "等待买家付款"}.get(
        order_status, "交易成功")


def upsert_refund_order(conn, row):
    """按 uk_refund_no(platform_type, refund_no) upsert。"""
    cols = ["platform_type", "shop_id", "refund_no", "order_no", "after_sale_type",
            "status", "refund_amount", "order_amount", "apply_time", "finish_time",
            "reason", "product_title", "sku_name", "item_id", "buyer_nick", "raw_json"]
    ph = ",".join(["%s"] * len(cols))
    upd = ",".join(f"{c}=VALUES({c})" for c in cols
                   if c not in ("platform_type", "refund_no"))
    sql = f"INSERT INTO refund_order ({','.join(cols)}) VALUES ({ph}) ON DUPLICATE KEY UPDATE {upd}"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])
    return 1


def refresh_derived_import_orders(conn, shop_id, platform_type, dfrom=None, dto=None):
    """从 order_info(全量订单) LEFT JOIN refund_order(退款) 派生写 refund_import_order。

    只增删 code=DERIVED_CODE 的行, 手传 Excel 行(code=雪花号)绝不动。

    DELETE 与 INSERT 同窗口: 有 dfrom/dto 时只删本窗口内订单的派生行
    (order_id IN (窗口内 order_info.order_no)), 否则(全量刷新)删本店本平台的全部标记行。
    """
    order_where = "o.platform_type=%s AND o.shop_id=%s AND o.is_deleted=0"
    order_params = [platform_type, shop_id]
    if dfrom:
        order_where += " AND o.create_time>=%s"
        order_params.append(dfrom)
    if dto:
        order_where += " AND o.create_time<DATE_ADD(%s, INTERVAL 1 DAY)"
        order_params.append(dto)
    with conn.cursor() as cur:
        del_sql = ("DELETE FROM refund_import_order "
                   "WHERE code=%s AND platform_type=%s AND shop_id=%s")
        del_params = [DERIVED_CODE, platform_type, shop_id]
        if dfrom or dto:
            del_sql += (" AND order_id IN (SELECT o.order_no FROM order_info o WHERE "
                        + order_where + ")")
            del_params += order_params
        cur.execute(del_sql, del_params)
        cur.execute(f"""
            SELECT o.order_no, o.total_amount, o.order_status,
                   COALESCE(r.refund_sum, 0) AS refund_sum
            FROM order_info o
            LEFT JOIN (SELECT order_no, SUM(refund_amount) AS refund_sum
                       FROM refund_order WHERE platform_type=%s GROUP BY order_no) r
              ON r.order_no = o.order_no
            WHERE {order_where}""", [platform_type] + order_params)
        rows = cur.fetchall()
        if not rows:
            return 0
        sql = ("INSERT INTO refund_import_order "
               "(code, order_id, pay_money, refund_money, order_status, platform_type, shop_id) "
               "VALUES (%s,%s,%s,%s,%s,%s,%s)")
        cur.executemany(sql, [
            (DERIVED_CODE, o, amt or 0, rs or 0, map_import_order_status(st), platform_type, shop_id)
            for (o, amt, st, rs) in rows])
    return len(rows)


def ensure_auto_report(conn, shop_id, platform_type, dfrom=None, dto=None):
    """确保存在一条 order_data_code=DERIVED_CODE 的退款分析报表, 供 UI「生成」消费派生行。

    MallRefundRecordServiceImpl.generate 按 order_data_code 读 refund_import_order,
    而派生行用 DERIVED_CODE 写入 —— 没有这张报表, 采集到的数据永远进不了「退款分析」页。
    幂等: 先 SELECT(本平台+本店), 有则原样返回其 id 不改动; 无则插一条 state=1(待生成)。
    返回报表 id。
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM refund_analysis_report "
            "WHERE order_data_code=%s AND platform_type=%s AND shop_id=%s ORDER BY id LIMIT 1",
            (DERIVED_CODE, platform_type, shop_id))
        row = cur.fetchone()
        if row:
            log(f"退款分析报表已存在: id={row[0]} (order_data_code={DERIVED_CODE})")
            return row[0]
        cur.execute(
            "INSERT INTO refund_analysis_report "
            "(code, name, start_time, end_time, total_amount, smart_promotion, crowd_promotion, "
            "site_promotion, keyword_promotion, order_data_code, state, create_by, create_time, "
            "del_flag, platform_type, shop_id) "
            "VALUES (%s,%s,%s,%s,0,0,0,0,0,%s,1,0,NOW(),0,%s,%s)",
            (DERIVED_CODE, "退款管理自动采集", dfrom, dto, DERIVED_CODE, platform_type, shop_id))
        new_id = cur.lastrowid
    log(f"已创建退款分析报表: id={new_id} (order_data_code={DERIVED_CODE})")
    return new_id
