#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""detect_stock_night.py — 夜间库存巡检（2026-10-19，spec onsale-refactor §3.3 M2 落地）

口径（owner 2026-10-19 指定）：
  - 宇宙 = 在售快照（sync_onsale 每日 12:40 产出的 onsale_snapshot 最新一天）
  - SKU 级详情页巡检只做【低库存】(source_stock ≤ --low-threshold 默认 10) 的在售商品
  - 已下架(快照货源状态) 直接标 source_status=0，不开页面
  - 另抽 --control 个健康商品开页面对照（控制台撒谎检测，不一致写 sync_alert onsale_mismatch）
  - 快照缺失 → 回退绑定池（taobao_offer_map + source_status=1，库存取 source_sku 最低值）

复用 detect_stock_change 的 fetch_offer / process_changes / mark_source_status，行为不变。
"""
import asyncio
import random
import re
import sys
import time

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')

from dbconf import DB_CONFIG
from offer_fetch import fetch_offer
from detect_stock_change import process_changes, mark_source_status


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def select_night_pool(rows, low_threshold=10, control_n=10, seed=0):
    """rows: [{'pid','offer','stock','status'}] → (inspect, control, dead)
    inspect = 销售中 且 (stock 未知 或 ≤low_threshold) —— 详情页 SKU 级巡检
    dead    = 已下架 —— 不开页面
    control = 其余销售中随机抽 control_n —— 控制台对照
    """
    inspect, dead, healthy = [], [], []
    for r in rows:
        st = (r.get("status") or "").strip()
        stock = r.get("stock")
        if st == "已下架":
            dead.append(r)
        elif st == "销售中" and (stock is None or stock <= low_threshold):
            inspect.append(r)
        elif st == "销售中":
            healthy.append(r)
    control = healthy[:]
    random.Random(seed).shuffle(control)
    return inspect, control[:max(0, control_n)], dead


def load_snapshot_rows():
    """onsale_snapshot 最新一天 → [{'pid','offer','stock','status'}]；无快照返回 []"""
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT os.source_product_id, os.source_stock, os.source_status, sp.source_product_url "
        "FROM onsale_snapshot os JOIN source_product sp ON sp.id = os.source_product_id "
        "WHERE os.snapshot_date = (SELECT MAX(snapshot_date) FROM onsale_snapshot)")
    rows = []
    for pid, stock, status, url in cur.fetchall():
        if pid is None:
            continue
        m = re.search(r"offer/(\d+)", url or "")
        if not m:
            continue
        rows.append({"pid": int(pid), "offer": m.group(1),
                     "stock": int(stock) if stock is not None else None,
                     "status": status or ""})
    cur.close()
    conn.close()
    return rows


def load_fallback_rows():
    """快照缺失回退：绑定+存活货源，库存取 source_sku 最低值"""
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT sp.id, MIN(ss.stock), sp.source_product_url FROM source_product sp "
        "JOIN taobao_offer_map tm ON tm.source_product_id = sp.id "
        "JOIN source_sku ss ON ss.source_product_id = sp.id AND ss.is_deleted=0 AND ss.status=1 "
        "WHERE sp.is_deleted=0 AND sp.source_status=1 "
        "AND sp.source_product_url LIKE '%detail.1688.com/offer/%' "
        "GROUP BY sp.id, sp.source_product_url")
    rows = []
    for pid, min_stock, url in cur.fetchall():
        m = re.search(r"offer/(\d+)", url or "")
        if m:
            rows.append({"pid": int(pid), "offer": m.group(1),
                         "stock": int(min_stock) if min_stock is not None else None,
                         "status": "销售中"})
    cur.close()
    conn.close()
    return rows


def write_mismatch_alert(pid, offer, snap_stock, detail_min):
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    today = time.strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(*) FROM sync_alert WHERE alert_type='onsale_mismatch' AND status=0 "
                "AND DATE(create_time)=%s", (today,))
    if cur.fetchone()[0]:
        cur.close()
        conn.close()
        return 0
    cur.execute("INSERT INTO sync_alert (alert_type, message, status, create_time) VALUES (%s,%s,0,NOW())",
                ("onsale_mismatch",
                 f"控制台库存与详情页不符: offer={offer} 快照={snap_stock} 实查={detail_min} "
                 f"(product={pid}，详情页为准，快照可能滞后)"))
    conn.commit()
    cur.close()
    conn.close()
    return 1


def mismatch(snap_stock, detail_min):
    if snap_stock is None or detail_min is None:
        return False
    return abs(detail_min - snap_stock) > max(20, snap_stock * 0.5)


async def run(args):
    from cdp_utils import connect_cdp
    rows = load_snapshot_rows()
    if rows:
        log(f"宇宙=在售快照 {len(rows)} 行")
    else:
        rows = load_fallback_rows()
        log(f"!! 快照缺失, 回退绑定池 {len(rows)} 行")
    inspect, control, dead = select_night_pool(rows, low_threshold=args.low_threshold,
                                               control_n=args.control, seed=int(time.strftime('%y%m%d')))
    log(f"巡检 {len(inspect)} / 对照 {len(control)} / 快照已下架 {len(dead)}")
    for r in dead:
        mark_source_status(r["pid"], 0)
    if dead:
        log(f"按快照标死 {len(dead)} 个 source_status=0")

    from cdp_utils import minimize_windows, new_page_quiet
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com"], log=log)
    page = await new_page_quiet(ctx)
    checked = changed = mismatches = 0
    try:
        try:
            await minimize_windows(ctx, log=lambda m: None)
        except Exception:
            pass
        todo = inspect + control
        for i, r in enumerate(todo):
            if args.stop_hour and int(time.strftime('%H')) >= args.stop_hour:
                log("硬停钟触发, 提前收工")
                break
            try:
                res = await asyncio.wait_for(fetch_offer(page, r["offer"]), timeout=60)
            except Exception as e:
                log(f"  ✗ product={r['pid']} offer={r['offer']} 抓取异常 {e!r}")
                continue
            if res.get("gone"):
                mark_source_status(r["pid"], 0)
                log(f"  ✗ product={r['pid']} offer={r['offer']} 已失效, source_status=0")
                continue
            skus = res.get("skus") or []
            if not skus:
                continue
            mark_source_status(r["pid"], 1)
            c, total = process_changes(r["pid"], skus)
            checked += 1
            changed += c
            detail_min = min(int(s.get("stock", 0)) for s in skus)
            is_control = i >= len(inspect)
            if is_control and mismatch(r["stock"], detail_min):
                mismatches += write_mismatch_alert(r["pid"], r["offer"], r["stock"], detail_min)
                log(f"  ⚠ 对照不符 product={r['pid']} 快照={r['stock']} 实查={detail_min}")
            await asyncio.sleep(args.delay)
        log(f"SUMMARY pool=night inspect={len(inspect)} control={len(control)} dead={len(dead)} "
            f"checked={checked} changed={changed} mismatch={mismatches}")
        return 0
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--low-threshold", type=int, default=10)
    ap.add_argument("--control", type=int, default=10)
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--stop-hour", type=int, default=5)
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
