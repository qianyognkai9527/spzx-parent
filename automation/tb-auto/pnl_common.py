#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实盈亏采集共用: 解析 / 状态映射 / 时间窗口 / 幂等落库写入器。

只读平台, 直连 db_spzx。DB_CONFIG 懒连接: import 期不碰库、不做任何网络 I/O。
"""
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
import pymysql  # noqa: E402
from dbconf import DB_CONFIG  # noqa: E402

PLATFORM_TAOBAO = 1

TRADE_STATUS_MAP = (
    ("交易成功", 3), ("交易关闭", -1), ("买家已付款", 1),
    ("等待买家付款", 0), ("待付款", 0),
    ("卖家已发货", 2), ("已发货", 2), ("等待卖家发货", 1), ("待发货", 1), ("交易中", 1),
)
PURCH_STATUS_MAP = (
    ("已成功", 3), ("已完成", 3), ("已发货", 2),
    ("待发货", 1), ("待打单", 1), ("待采购", 1),
    ("退款中", -1), ("已关闭", -1), ("已取消", -1),
)
MONEY_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
MONEY_TOKEN_RE = re.compile(r"[￥¥]\s*([0-9]+(?:\.[0-9]+)?)")
DT_RE = re.compile(r"(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d)")
ORDER_NO_RE = re.compile(r"(\d{15,20})")
FREIGHT_RE = re.compile(r"含运费\s*[￥¥]?\s*([0-9]+(?:\.[0-9]+)?)")
# ISV 行 innerText 里 采购单号 标签与号码之间被 \n -> " / " 归一化插入分隔符
# (实测形如 "采购单号： / 5127345723001028719"), 故分隔符需允许 [\s/]。
PURCH_ORDER_RE = re.compile(r"采购单号[：:]?[\s/]*(\d{6,})")


def log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


def parse_money(s):
    if s is None:
        return None
    m = MONEY_RE.search(str(s))
    return Decimal(m.group(1)) if m else None


def parse_int(s):
    if s is None:
        return None
    m = MONEY_RE.search(str(s).replace(",", ""))
    return int(Decimal(m.group(1))) if m else None


def parse_dt(s):
    if not s:
        return None
    m = DT_RE.search(str(s))
    return m.group(1) if m else None


def _map(text, table, default):
    t = text or ""
    for k, v in table:
        if k in t:
            return v
    return default


def _first_status_text(text, table):
    """返回 table 里第一个命中的**关键词字符串**, 找不到返回 None。

    与 _map 的区别: _map 映射成 int; 这里保留原文, 供生产端产出、消费端再映射。
    """
    t = text or ""
    for k, _v in table:
        if k in t:
            return k
    return None


def map_trade_status(text):
    return _map(text, TRADE_STATUS_MAP, 0)


def map_purch_status(text):
    return _map(text, PURCH_STATUS_MAP, 0)


def _add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def quarter_windows(dfrom, dto):
    """从 dfrom 起按 3 个自然月切窗, 末窗被 dto 截断。返回 [(start, end), ...]。"""
    start = datetime.strptime(dfrom, "%Y-%m-%d").date()
    end = datetime.strptime(dto, "%Y-%m-%d").date()
    if start > end:
        return []
    out, cur = [], start
    while cur <= end:
        w_end = min(_add_months(cur, 3) - timedelta(days=1), end)
        out.append((cur.isoformat(), w_end.isoformat()))
        cur = _add_months(cur, 3)
    return out


def parse_sold_cells(cells):
    """淘宝已卖出宝贝一行 (8 个有效 td) → 解析 dict; 无订单号返回 None。"""
    if not cells or len(cells) < 8:
        return None
    head = cells[1] or ""
    m = ORDER_NO_RE.search(head)
    if not m:
        return None
    body = cells[2] or ""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    title = lines[0] if lines else None
    sku = "；".join(ln for ln in lines[1:] if not ln.startswith("商家编码"))
    return {
        "order_no": m.group(1),
        "create_time": parse_dt(head),
        "title": title,
        "sku_name": (sku or None),
        "unit_price": parse_money(cells[3]),
        "qty": parse_int(cells[4]),
        "after_sale_status": (cells[5] or "").strip() or None,
        "trade_status": (cells[6] or "").replace("详情", "").strip(),
        "real_pay": parse_money(cells[7]),
    }


def build_order_info_row(p, shop_id):
    remark = None
    if p.get("after_sale_status"):
        remark = f"履约/售后状态={p['after_sale_status']}"[:500]
    return {
        "order_no": p["order_no"],
        "order_status": map_trade_status(p.get("trade_status")),
        "total_amount": p["real_pay"] if p["real_pay"] is not None else Decimal("0.00"),
        "original_total_amount": p["real_pay"] if p["real_pay"] is not None else Decimal("0.00"),
        "receiver_name": None,
        "receiver_phone": None,
        "receiver_address": None,
        "remark": remark,
        "platform_type": PLATFORM_TAOBAO,
        "shop_id": shop_id if shop_id is not None else 0,
        "create_time": p.get("create_time"),
    }


def build_order_item_row(p):
    return {
        "product_title": p.get("title"),
        "sku_name": p.get("sku_name"),
        "sku_price": p["unit_price"],
        "sku_num": p["qty"],
        "platform_type": PLATFORM_TAOBAO,
    }


def parse_isv_row(shop_order_no, source_product_id, taobao_title, raw):
    """ISV 一行 → dict。source_order_no(1688 采购单号) 找不到时留 None, 由写入器跳过并计数。

    契约(与 build_source_relation_row 配套): `purch_status` 这里是**原始关键词字符串**
    (如 "已成功"/None), 不在此处映射成 int —— 映射只由 build_source_relation_row 做一次。

    金额区分(实测 ISV 行格式, 2026-10-12 Task 3): 淘宝售价一个 `¥X`, 1688 采购金额写成
    `￥X / （含运费￥Y）` —— 货款与 `（含运费` 之间被 \n->" / " 归一化隔开。
    这里按"金额后 <=12 字符内出现 含运费"判为货款、其余第一个为淘宝售价, 并跳过运费金额本身。
    (12 字符窗口的实测样本见 test_pnl_common.py 的 `_raw_live` 与 `真实 ISV 行格式` 两处夹具。)
    """
    raw = raw or ""
    fm = FREIGHT_RE.search(raw)
    free_span = fm.span() if fm else None

    purch_amount = None
    taobao_price = None
    for m in MONEY_TOKEN_RE.finditer(raw):
        if free_span and free_span[0] <= m.start() < free_span[1]:
            continue  # 这是运费金额, 不算货款/售价
        amount = Decimal(m.group(1))
        tail = raw[m.end():m.end() + 12]
        if purch_amount is None and "含运费" in tail:
            purch_amount = amount
        elif taobao_price is None:
            taobao_price = amount

    so = PURCH_ORDER_RE.search(raw)
    return {
        "shop_order_no": shop_order_no,
        "source_order_no": so.group(1) if so else None,
        "order_time": parse_dt(raw),
        "source_product_id": source_product_id,
        "taobao_title": taobao_title,
        "taobao_price": taobao_price,
        "purch_amount": purch_amount,
        "source_freight": Decimal(fm.group(1)) if fm else None,
        "purch_status": _first_status_text(raw, PURCH_STATUS_MAP),
        "remark": None,
    }


def build_source_relation_row(isv):
    return {
        "order_no": isv["shop_order_no"],
        "source_order_no": isv.get("source_order_no"),
        "platform_type": PLATFORM_TAOBAO,
        "platform_product_id": None,
        "platform_product_code": None,
        "platform_product_title": isv.get("taobao_title"),
        "platform_selling_price": isv.get("taobao_price"),
        "platform_freight": None,
        "source_product_id": (int(isv["source_product_id"])
                              if str(isv.get("source_product_id") or "").isdigit() else None),
        "source_product_code": None,
        "source_product_title": isv.get("taobao_title"),
        "source_selling_price": isv.get("purch_amount"),
        "source_freight": isv.get("source_freight"),
        "order_status": map_purch_status(isv.get("purch_status")),
        "order_time": isv.get("order_time"),
        "remark": isv.get("remark"),
    }


def brush_candidates(order_rows, related_order_nos):
    return [r for r in order_rows if r["order_no"] not in related_order_nos]


def connect_db():
    return pymysql.connect(**DB_CONFIG)


def upsert_order_info(conn, row):
    """按 uk_order_no(order_no) upsert, 返回 order_info.id。

    只发 SQL, **调用方必须自己 `conn.commit()`** (pymysql autocommit=False)。
    create_time 可空: 为空时**不进列清单**, 让列默认值 CURRENT_TIMESTAMP 生效,
    绝不写 create_time=NULL(NOT NULL 列)。
    """
    cols = ["order_no", "order_status", "total_amount", "original_total_amount",
            "receiver_name", "receiver_phone", "receiver_address", "remark",
            "platform_type", "shop_id"]
    vals = [row.get(c) for c in cols]
    if row.get("create_time"):
        cols.append("create_time")
        vals.append(row["create_time"])
    cols.append("update_time")
    vals.append(datetime.now())

    ph = ",".join(["%s"] * len(cols))
    upd = ",".join(f"{c}=VALUES({c})" for c in cols if c != "order_no")
    sql = (f"INSERT INTO order_info ({','.join(cols)}) VALUES ({ph}) "
           f"ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        cur.execute(sql, vals)
        cur.execute("SELECT id FROM order_info WHERE order_no=%s", (row["order_no"],))
        return cur.fetchone()[0]


def upsert_order_item(conn, order_id, item):
    """order_item 无自然唯一键 → 先查后写, 幂等键 (order_id, sku_name)。

    只发 SQL, **调用方必须自己 `conn.commit()`** (pymysql autocommit=False)。
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM order_item WHERE order_id=%s AND sku_name<=>%s",
                    (order_id, item.get("sku_name")))
        got = cur.fetchone()
        if got:
            cur.execute("UPDATE order_item SET product_title=%s, sku_price=%s, sku_num=%s, "
                        "platform_type=%s, update_time=NOW() WHERE id=%s",
                        (item.get("product_title"), item.get("sku_price"), item.get("sku_num"),
                         item.get("platform_type"), got[0]))
            return got[0]
        cur.execute("INSERT INTO order_item (order_id, product_title, sku_name, sku_price, sku_num, "
                    "platform_type, create_time, update_time) VALUES (%s,%s,%s,%s,%s,%s,NOW(),NOW())",
                    (order_id, item.get("product_title"), item.get("sku_name"),
                     item.get("sku_price"), item.get("sku_num"), item.get("platform_type")))
        return cur.lastrowid


def set_order_items_item_id(conn, order_id, item_id):
    """把某订单下所有 order_item 的权威 item_id 写上。只发 SQL, 调用方自己 commit。"""
    with conn.cursor() as cur:
        cur.execute("UPDATE order_item SET item_id=%s, update_time=NOW() WHERE order_id=%s",
                    (item_id, order_id))
        return cur.rowcount


def upsert_source_relation(conn, row):
    """按 uk_platform_order_source(platform_type, order_no, source_order_no) upsert。

    只发 SQL, **调用方必须自己 `conn.commit()`** (pymysql autocommit=False)。
    """
    if not row.get("source_order_no"):
        return 0
    cols = ["order_no", "source_order_no", "platform_type", "platform_product_id",
            "platform_product_code", "platform_product_title", "platform_selling_price",
            "platform_freight", "source_product_id", "source_product_code",
            "source_product_title", "source_selling_price", "source_freight",
            "order_status", "order_time", "remark"]
    ph = ",".join(["%s"] * len(cols))
    upd = ",".join(f"{c}=VALUES({c})" for c in cols
                   if c not in ("order_no", "source_order_no", "platform_type"))
    sql = (f"INSERT INTO order_source_relation ({','.join(cols)}) VALUES ({ph}) "
           f"ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])
    return 1


def upsert_promo_account_daily(conn, row):
    """按 uk_promo_daily(shop_id, plan_type, campaign_id, stat_date) upsert。

    只发 SQL, **调用方必须自己 `conn.commit()`** (pymysql autocommit=False)。
    """
    cols = ["shop_id", "platform_code", "stat_date", "plan_type", "campaign_id",
            "campaign_name", "report_source", "charge"]
    ph = ",".join(["%s"] * len(cols))
    upd = ",".join(f"{c}=VALUES({c})" for c in ("campaign_name", "charge"))
    sql = (f"INSERT INTO promo_cost_daily ({','.join(cols)}) VALUES ({ph}) "
           f"ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])
    return 1


def merge_offer_items(osr_pairs, jsonl_pairs):
    """offer → [item_id,...]: OSR(订单时点证据)在前, ISV商品管理(现绑定)去重并入。

    返回 (mapping, conflicts): conflicts=[(offer, 首个osr_item, 新jsonl_item)]。
    空 offer/item 一律丢弃; 同 offer 多 item 全部保留(配对循环逐个试)。
    """
    mapping = {}
    conflicts = []
    for off, it in osr_pairs:
        off, it = str(off) if off else "", str(it) if it else ""
        if not off or not it:
            continue
        lst = mapping.setdefault(off, [])
        if it not in lst:
            lst.append(it)
    for off, it in jsonl_pairs:
        off, it = str(off) if off else "", str(it) if it else ""
        if not off or not it:
            continue
        lst = mapping.setdefault(off, [])
        if it in lst:
            continue
        if lst:
            conflicts.append((off, lst[0], it))
        lst.append(it)
    return mapping, conflicts
