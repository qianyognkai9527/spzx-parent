#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 1688 买家采购订单（全历史）→ purchase_order_1688。

来源: mtop.1688.trading.dataline.service / OrderListDataLineService.buyerOrderList
（「已买到的货品」列表接口, sign 自算: md5(token&t&appKey&data), token 取 _m_h5_tk cookie）。
为什么不用 ISV: ISV 分销工作台对本店只保留 204 单(2024-10-18 起), 买家采购订单才是全量(实测 1562 单)。

只读: 只调列表查询接口, 不碰任何写接口。
跑法:
  automation/venv/bin/python tb-auto/collect_1688_buyer_orders.py --dry-run
  automation/venv/bin/python tb-auto/collect_1688_buyer_orders.py
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import connect_db, log  # noqa: E402

API = "mtop.1688.trading.dataline.service"
APPKEY = "12574478"
H5 = f"https://h5api.m.1688.com/h5/{API}/1.0/"
REFERER = "https://air.1688.com/app/ctf-page/trade-order-list/buyer-order-list.html?page=1&pageSize=10"
SERVICE = "OrderListDataLineService.buyerOrderList"
PROGRESS = os.path.join(BASE, "buyer_orders_progress.json")
PAGE_SIZE = 100

CENT = re.compile(r"^-?\d+$")


def read_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            return json.load(f)
    return {"pages_done": []}


def save_progress(pg):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(pg, f, ensure_ascii=False)


def yuan(v):
    """接口金额是「分」字符串 → 元 Decimal。"""
    from decimal import Decimal
    if v is None or v == "":
        return None
    s = str(v)
    if not CENT.match(s):
        return None
    return (Decimal(s) / 100).quantize(Decimal("0.01"))


def parse_dt(v):
    if not v:
        return None
    s = str(v)
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", s)
    return m.group(1) if m else None


def build_row(o):
    entries = []
    for e in (o.get("orderEntries") or []):
        q = e.get("quantity")
        if isinstance(q, dict):   # 有时 quantity 是 {realAmount:1,...}
            q = q.get("realAmountStr") or q.get("calAmount")
        entries.append({
            "sourceId": e.get("sourceId"),
            "productName": e.get("productName"),
            "quantity": q,
            "amount": str(yuan(e.get("amount")) or ""),
            "unitPrice": str(yuan(e.get("actualUnitPrice")) or ""),
            "specInfo": e.get("specInfo"),
            "skuId": e.get("skuId"),
        })
    seller = o.get("sellerInfo") or {}
    return {
        "order_no": str(o.get("idStr") or o.get("id") or ""),
        "gmt_create": parse_dt(o.get("gmtCreate")),
        "gmt_payment": None,   # gmtPayment 是毫秒时间戳, 单独转
        "sum_payment": yuan(o.get("sumPayment")),
        "sum_product_payment": yuan(o.get("sumProductPayment")),
        "carriage": yuan(o.get("carriage")),
        "status": o.get("status"),
        "status_label": o.get("statusLabel"),
        "seller_login_id": seller.get("loginId"),
        "entries_json": json.dumps(entries, ensure_ascii=False),
        "raw_json": json.dumps(o, ensure_ascii=False),
    }


async def mtop_call(ctx, data_obj, tries=4, log=print):
    for attempt in range(tries):
        token = ""
        for c in await ctx.cookies("https://h5api.m.1688.com"):
            if c["name"] == "_m_h5_tk":
                token = c["value"].split("_")[0]
                break
        t = str(int(time.time() * 1000))
        data_str = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))
        sign = hashlib.md5(f"{token}&{t}&{APPKEY}&{data_str}".encode()).hexdigest()
        url = (f"{H5}?jsv=2.7.4&appKey={APPKEY}&t={t}&sign={sign}&ecode=1&type=json"
               f"&valueType=string&api={API}&v=1.0&dataType=json")
        r = await ctx.request.post(
            url, data=("data=" + urllib.parse.quote(data_str)),
            headers={"content-type": "application/x-www-form-urlencoded", "referer": REFERER},
            timeout=30000)
        body = await r.text()
        try:
            j = json.loads(body)
        except Exception:
            log(f"  非JSON响应 len={len(body)}: {body[:100]}")
            await asyncio.sleep(2)
            continue
        ret = j.get("ret") or []
        if any("SUCCESS" in x for x in ret):
            return j
        log(f"  ret={ret} (attempt {attempt + 1})")
        await asyncio.sleep(2)   # token 过期时 Set-Cookie 刷新, 重试用新 token
    return None


def dig_result(j):
    d = (j.get("data") or {}).get("data")
    if isinstance(d, dict) and isinstance(d.get("result"), str):
        try:
            return json.loads(d["result"])
        except Exception:
            return None
    return None


def upsert(conn, row):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM purchase_order_1688 WHERE order_no=%s", (row["order_no"],))
        got = cur.fetchone()
        cols = ["order_no", "gmt_create", "gmt_payment", "sum_payment", "sum_product_payment",
                "carriage", "status", "status_label", "seller_login_id", "entries_json", "raw_json"]
        vals = [row.get(c) for c in cols]
        if got:
            sets = ",".join(f"{c}=%s" for c in cols[1:])
            cur.execute(f"UPDATE purchase_order_1688 SET {sets}, update_time=NOW() WHERE id=%s",
                        vals[1:] + [got[0]])
            return 0
        cur.execute(f"INSERT INTO purchase_order_1688 ({','.join(cols)}) "
                    f"VALUES ({','.join(['%s'] * len(cols))})", vals)
        return 1


async def run(args):
    b, ctx = await connect_cdp(9222, keep_urls=["1688.com", "ufuwu.1688.com"], log=log)
    conn = None if args.dry_run else connect_db()
    pg = read_progress()
    stats = {"pages": 0, "orders": 0, "written": 0, "skipped_pages": 0}
    try:
        page = 1
        total = pages = None
        while page <= args.max_pages:
            if (not args.force) and str(page) in pg["pages_done"] and not args.dry_run:
                stats["skipped_pages"] += 1
                page += 1
                continue
            data = {"serviceId": SERVICE,
                    "param": json.dumps({"page": page, "pageSize": PAGE_SIZE}, separators=(",", ":"))}
            j = await mtop_call(ctx, data, log=log)
            if not j:
                log(f"第{page}页调用失败, 停止")
                break
            inner = dig_result(j) or {}
            dd = inner.get("data") or {}
            orders = dd.get("data") or []
            total = int(dd.get("total") or 0)
            pages = int(dd.get("pages") or 0)
            if not orders:
                log(f"第{page}页 0 单, 结束")
                break
            for o in orders:
                stats["orders"] += 1
                row = build_row(o)
                gp = o.get("gmtPayment")
                if isinstance(gp, (int, str)) and str(gp).isdigit():
                    row["gmt_payment"] = datetime.fromtimestamp(int(gp) / 1000).strftime("%Y-%m-%d %H:%M:%S")
                if args.dry_run:
                    e = (row["entries_json"] and json.loads(row["entries_json"]) or [{}])[0]
                    if page == 1 and stats["orders"] <= 5:
                        log(f"  [dry] {row['order_no']} {row['gmt_create']} ¥{row['sum_payment']} "
                            f"(运费¥{row['carriage']}) {row['status_label']} offer={e.get('sourceId')} "
                            f"{e.get('productName','')[:14]}")
                else:
                    stats["written"] += upsert(conn, row)
            if not args.dry_run:
                conn.commit()
                pg["pages_done"].append(str(page))
                save_progress(pg)
            stats["pages"] += 1
            log(f"第{page}/{pages}页: {len(orders)} 单 (total={total})")
            if page >= pages:
                break
            page += 1
            await asyncio.sleep(args.delay)
        log(f"完成: 翻 {stats['pages']} 页 / 订单 {stats['orders']} / 新写 {stats['written']} / "
            f"跳过已完成页 {stats['skipped_pages']} (total={total})")
        if stats["orders"] == 0:
            log("!! 0 单(登录态/接口异常?) → 退出码 3")
            return 3
        return 0
    finally:
        if conn:
            conn.close()
        await b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--force", action="store_true", help="忽略进度重翻")
    args = ap.parse_args()
    attempts = 0
    while True:
        try:
            sys.exit(asyncio.run(run(args)))
        except SystemExit:
            raise
        except Exception as e:
            attempts += 1
            log(f"运行异常(第{attempts}次): {type(e).__name__}: {str(e)[:160]}")
            if attempts >= 3:
                log("重试次数用尽, 退出(进度保留)")
                sys.exit(1)
            time.sleep(8)


if __name__ == "__main__":
    main()
