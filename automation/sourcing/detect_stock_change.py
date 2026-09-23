#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量变化检测: 采集 1688 SKU -> 与上次 source_sku 对比 -> 有变化的写 inventory_change_log -> 更新 stock。
用法: detect_stock_change.py [--limit N] [--test]"""
import asyncio
import json
import re
import sys
import time
from datetime import datetime

import pymysql
from playwright.async_api import async_playwright

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
CDP = "http://127.0.0.1:9222"
SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"
PROGRESS_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/detect_stock_pool_progress.json"
FETCH_TIMEOUT = 25  # 单个商品抓取超时(秒)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_products(limit, test, pool):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    if pool:
        # 优质池: 优质货品(A/B) OR 优质供应商(A/B)旗下货品
        sql = (
            "SELECT id, source_product_url FROM source_product sp "
            "WHERE sp.is_deleted=0 AND sp.source_product_url LIKE '%detail.1688.com/offer/%' "
            "AND (sp.quality_grade IN ('A','B') OR EXISTS ("
            "  SELECT 1 FROM source_factory f WHERE f.id=sp.source_factory_id "
            "  AND f.is_deleted=0 AND f.quality_grade IN ('A','B')))"
        )
    else:
        sql = "SELECT id, source_product_url FROM source_product WHERE is_deleted=0 AND source_product_url LIKE '%detail.1688.com/offer/%'"
    if test:
        sql += " LIMIT 3"
    elif limit:
        sql += f" LIMIT {limit}"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    out = []
    for pid, url in rows:
        m = re.search(r"offer/(\d+)", url or "")
        if m:
            out.append((pid, m.group(1)))
    return out


def get_old_skus(product_id):
    """返回 {sku_key: (id, stock)} 上次快照"""
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, sku_key, stock FROM source_sku WHERE source_product_id=%s AND is_deleted=0 AND status=1", (product_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {k: (sid, st) for sid, k, st in rows}


async def fetch_source_skus(page, offer_id):
    captured = {}

    async def on_resp(r):
        if SKU_API in r.url:
            try:
                captured["body"] = await r.text()
            except Exception:
                pass

    page.on("response", lambda r: asyncio.create_task(on_resp(r)))
    await page.goto(f"https://detail.1688.com/offer/{offer_id}.html", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    if "body" not in captured:
        return []
    try:
        data = json.loads(captured["body"])
        m = data.get("data", {}).get("skuSelectorBizModel", {})
        info = m.get("skuInfoMap", {})
    except Exception:
        return []
    out = []
    for key, sv in info.items():
        if not isinstance(sv, dict):
            continue
        out.append({
            "sku_key": key.replace("&gt;", ">"),
            "sku_id": str(sv.get("skuId", "")),
            "stock": int(sv.get("canBookCount", 0)),
            "price": float(sv.get("price", 0)),
            "spec_id": str(sv.get("specId", "")),
        })
    return out


def process_changes(product_id, new_skus):
    """对比新旧, 写流水, 更新 source_sku。返回 (changed, total)"""
    old = get_old_skus(product_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    changed = 0
    for s in new_skus:
        old_data = old.get(s["sku_key"])
        if old_data:
            old_id, old_stock = old_data
            if old_stock != s["stock"]:
                change = s["stock"] - old_stock
                # 写流水
                cur.execute("INSERT INTO inventory_change_log (source_sku_id, source_product_id, old_stock, new_stock, change_amount, change_type, sync_time, create_time) "
                            "VALUES (%s,%s,%s,%s,%s,'auto',%s,%s)",
                            (old_id, product_id, old_stock, s["stock"], change, now, now))
                # 更新 stock
                cur.execute("UPDATE source_sku SET stock=%s, price=%s, update_time=%s WHERE id=%s",
                            (s["stock"], s["price"], now, old_id))
                changed += 1
        else:
            # 新 SKU, 插入
            cur.execute("INSERT INTO source_sku (source_product_id, sku_key, sku_id, spec_id, stock, price, status, create_time, update_time) "
                        "VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)",
                        (product_id, s["sku_key"], s["sku_id"], s["spec_id"], s["stock"], s["price"], now, now))
            changed += 1
    conn.commit()
    cur.close()
    conn.close()
    return changed, len(new_skus)


def load_progress():
    try:
        import os
        if os.path.exists(PROGRESS_FILE):
            return set(json.load(open(PROGRESS_FILE)).get("done", []))
    except Exception:
        pass
    return set()


def save_progress(done):
    json.dump({"done": sorted(done)}, open(PROGRESS_FILE, "w"))


def ensure_guard_tab():
    """浏览器至少留1个标签, 防 0 target 导致下次 connect 报 Browser context management not supported"""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:9222/json/new?https://www.taobao.com", method='PUT')
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


async def main():
    test = "--test" in sys.argv
    pool = "--pool" in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    products = load_products(limit, test, pool)
    done = load_progress()
    todo = [(pid, oid) for pid, oid in products if pid not in done]
    log(f"待检测 {len(todo)}/{len(products)} 个商品" + (" (优质池)" if pool else "") + " (续跑跳过{}个)".format(len(products) - len(todo)))
    async with async_playwright() as pw:
        b = await pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        total_changed = 0
        sku_counts_file = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/sku_counts.json"
        try:
            sku_counts = json.load(open(sku_counts_file)) if __import__("os").path.exists(sku_counts_file) else {}
        except Exception:
            sku_counts = {}
        for pid, offer_id in todo:
            try:
                skus = await asyncio.wait_for(fetch_source_skus(page, offer_id), timeout=FETCH_TIMEOUT)
                changed, total = process_changes(pid, skus)
                total_changed += changed
                if skus:
                    sku_counts[offer_id] = {"count": len(skus), "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
                if changed:
                    log(f"  product={pid} offer={offer_id} -> {changed}/{total} SKU 有变化")
            except asyncio.TimeoutError:
                log(f"  ✗ product={pid} 抓取超时({FETCH_TIMEOUT}s), 跳过")
            except Exception as e:
                log(f"  ✗ product={pid} 异常: {str(e)[:80]}")
            done.add(pid)
            save_progress(done)
            if len(done) % 20 == 0:
                json.dump(sku_counts, open(sku_counts_file, "w"), ensure_ascii=False)
            await asyncio.sleep(2)
        json.dump(sku_counts, open(sku_counts_file, "w"), ensure_ascii=False)
        ensure_guard_tab()
        await page.close()
    log(f"完成: {total_changed} 个 SKU 有变化, 已写流水")


if __name__ == "__main__":
    asyncio.run(main())
