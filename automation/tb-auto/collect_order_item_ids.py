#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回填 order_item.item_id —— 每单权威商品id。

来源: 淘宝订单快照页 `trade.taobao.com/trade/detail/tradeSnap.htm?tradeID=<订单号>&snapShot=true`
内嵌 JSON 的 `itemSnapDO.itemId`。这是唯一对**任意订单**(不论是否退款)可得的权威 item_id:
已卖出宝贝列表/订单详情页均不暴露 item_id(只给标题/商家编码), 退款页只覆盖退款单。

为什么不用「标题→item_id」: 改过标题的商品会把同一 item 的订单拆到多个 key,
分母漏计 → 退款率虚高。itemSnapDO.itemId 不受改标题影响。

只读: 只用浏览器请求上下文 GET 快照页, 不导航、不点任何按钮、不写平台。
落库: 幂等 UPDATE order_item SET item_id(按 order_id), 断点续跑。

跑法:
  automation/venv/bin/python tb-auto/collect_order_item_ids.py --dry-run --limit 20
  automation/venv/bin/python tb-auto/collect_order_item_ids.py --from 2024-10-01
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import (connect_db, log, set_order_items_item_id)  # noqa: E402

PORT = 9222
PROGRESS = os.path.join(BASE, "order_item_ids_progress.json")
SNAP = ("https://trade.taobao.com/trade/detail/tradeSnap.htm?tradeID={oid}&snapShot=true")
HDRS = {
    "referer": "https://myseller.taobao.com/home.htm/trade-platform/tp/sold",
    "user-agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
# itemSnapDO 内嵌 JSON 被转义, itemId 的引号可能是 \" 或 "; 值必为 8+ 位数字
ITEM_ID_RE = re.compile(r'itemSnapDO.*?itemId\\?"?\s*:\s*(\d{8,})', re.S)


def read_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            pg = json.load(f)
    else:
        pg = {}
    pg.setdefault("done", {})   # {order_no: item_id or ""}
    return pg


def save_progress(pg):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(pg, f, ensure_ascii=False, indent=2)


def load_orders(conn, dfrom, dto):
    """返回 [(order_no, order_id, item_id)]。

    只取付费单(order_status IN (1,2,3)): **交易关闭(=-1)的单没有交易快照**
    (tradeSnap 不返回 itemSnapDO, 实测), 但关闭单只有「有退款」才计入分母,
    其 item_id 由 refund_order.item_id 提供(见 refund_product_report.py)。
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT o.order_no, o.id, MAX(oi.item_id)
            FROM order_info o JOIN order_item oi ON oi.order_id=o.id
            WHERE o.platform_type=1 AND o.is_deleted=0 AND o.order_status IN (1,2,3)
              AND o.create_time>=%s AND o.create_time<DATE_ADD(%s, INTERVAL 1 DAY)
            GROUP BY o.order_no, o.id
            ORDER BY o.create_time""", (dfrom, dto))
        return cur.fetchall()


async def fetch_item_id(ctx, order_no, tries=2):
    """GET 快照页抽 itemSnapDO.itemId。

    返回 (item_id|None, status):
      ("<id>"|"", "ok")        = 有快照(item_id 可能为空串, 极少)
      (None, "no_snapshot")    = 旧壳/无快照(确定性缺失, 不再重试; 由标题映射兜底)
      (None, "fail")           = 全程异常(网络/CDP), 下轮重试
    """
    url = SNAP.format(oid=order_no)
    saw_response = False
    for _ in range(tries):
        try:
            r = await ctx.request.get(url, timeout=25000, headers=HDRS)
            body = (await r.body()).decode("gbk", "replace")
        except Exception as e:
            log(f"  取快照异常 {order_no}: {type(e).__name__}: {str(e)[:80]}")
            await asyncio.sleep(2)
            continue
        saw_response = True
        if "itemSnapDO" in body:
            m = ITEM_ID_RE.search(body)
            return (m.group(1) if m else ""), "ok"
        await asyncio.sleep(1)
    return None, ("no_snapshot" if saw_response else "fail")


async def run(args):
    conn = None if args.dry_run else connect_db()
    pg = read_progress()
    b, ctx = await connect_cdp(PORT, keep_urls=["myseller.taobao.com", "taobao.com"], log=log)
    try:
        if conn is None:
            # dry-run 也要订单列表: 临时连一次只读
            tmp = connect_db()
            try:
                orders = load_orders(tmp, args.dfrom, args.dto)
            finally:
                tmp.close()
        else:
            orders = load_orders(conn, args.dfrom, args.dto)
        todo = []
        for order_no, oid, cur_item in orders:
            done_val = pg["done"].get(order_no, "__none__")
            if (not args.force) and done_val != "__none__":
                continue
            if (not args.force) and cur_item:
                pg["done"][order_no] = str(cur_item)
                continue
            todo.append((order_no, oid))
        if args.limit:
            todo = todo[:args.limit]
        log(f"订单 {len(orders)} 单, 待回填 {len(todo)} 单")

        ok = miss = fail = 0
        for i, (order_no, oid) in enumerate(todo, 1):
            item_id, status = await fetch_item_id(ctx, order_no)
            if status == "fail":
                fail += 1
                log(f"  [{i}/{len(todo)}] {order_no} 异常(本次不标记 done)")
                await asyncio.sleep(args.delay)
                continue
            if item_id:
                ok += 1
            else:
                miss += 1
            if args.dry_run:
                tag = item_id or ("(无快照)" if status == "no_snapshot" else "(空)")
                log(f"  [dry] [{i}/{len(todo)}] {order_no} -> item_id={tag}")
            else:
                if item_id:
                    set_order_items_item_id(conn, oid, item_id)
                conn.commit()
                # no_snapshot: 记 "" 避免每轮重试(确定性缺失, 由标题映射兜底)
                pg["done"][order_no] = item_id or ""
                if i % 20 == 0:
                    save_progress(pg)
            await asyncio.sleep(args.delay)
        if not args.dry_run:
            save_progress(pg)
        log(f"完成: 命中 {ok} / 无itemId {miss} / 失败 {fail} (待回填 {len(todo)})")
        if todo and fail == len(todo):
            log("全部失败 → 退出码 1")
            return 1
        return 0
    finally:
        if conn:
            conn.close()
        await b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--to", dest="dto", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.3, help="每单间隔秒(防风控)")
    ap.add_argument("--force", action="store_true", help="忽略进度/已有 item_id 重取")
    ap.add_argument("--dry-run", action="store_true")
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
            if attempts >= 4:
                log("重试次数用尽, 退出(进度保留)")
                sys.exit(1)
            time.sleep(10)


if __name__ == "__main__":
    main()
