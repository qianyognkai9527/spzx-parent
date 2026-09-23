#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 1688 货源 SKU 到 source_sku 表(读 skuInfoMap 接口)。
用法: collect_source_sku.py [--limit N] [--test]
--test: 只采前 3 个商品"""
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


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_products(limit, test):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
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


async def fetch_source_skus(page, offer_id):
    """打开 1688 详情页, 捕获 skuInfoMap, 返回 [{sku_key, sku_id, stock, price, spec_id}]"""
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
        sku_key = key.replace("&gt;", ">")
        out.append({
            "sku_key": sku_key,
            "sku_id": str(sv.get("skuId", "")),
            "stock": int(sv.get("canBookCount", 0)),
            "price": float(sv.get("price", 0)),
            "spec_id": str(sv.get("specId", "")),
        })
    return out


def upsert_skus(product_id, skus):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for s in skus:
        cur.execute(
            "SELECT id, stock FROM source_sku WHERE source_product_id=%s AND sku_key=%s AND is_deleted=0",
            (product_id, s["sku_key"]),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE source_sku SET sku_id=%s, spec_id=%s, stock=%s, price=%s, status=1, update_time=%s WHERE id=%s",
                (s["sku_id"], s["spec_id"], s["stock"], s["price"], now, row[0]),
            )
        else:
            cur.execute(
                "INSERT INTO source_sku (source_product_id, sku_key, sku_id, spec_id, stock, price, status, create_time, update_time) "
                "VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)",
                (product_id, s["sku_key"], s["sku_id"], s["spec_id"], s["stock"], s["price"], now, now),
            )
    # 本次未出现的 SKU 标记下架(status=0)
    if skus:
        keys = [s["sku_key"] for s in skus]
        placeholders = ",".join(["%s"] * len(keys))
        cur.execute(
            f"UPDATE source_sku SET status=0, update_time=%s WHERE source_product_id=%s AND sku_key NOT IN ({placeholders}) AND is_deleted=0",
            [now, product_id] + keys,
        )
    conn.commit()
    cur.close()
    conn.close()


async def main():
    test = "--test" in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    products = load_products(limit, test)
    log(f"待采集 {len(products)} 个 1688 商品")
    async with async_playwright() as pw:
        b = await pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        done = 0
        for pid, offer_id in products:
            try:
                skus = await fetch_source_skus(page, offer_id)
                upsert_skus(pid, skus)
                done += 1
                log(f"  [{done}/{len(products)}] product={pid} offer={offer_id} -> {len(skus)} sku")
            except Exception as e:
                log(f"  ✗ product={pid} offer={offer_id} 异常: {str(e)[:80]}")
            await asyncio.sleep(2)
        await page.close()
    log(f"完成: 采集 {done}/{len(products)} 个商品")


if __name__ == "__main__":
    asyncio.run(main())
