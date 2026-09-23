"""collect_1688_full.py - 合并版: 一次详情页访问抓 SKU+库存+运费
合并了 collect_source_sku.py 和 fetch_freight.py 的功能
用法: python collect_1688_full.py [--limit N] [--test]
  --test: 只采前3个验证
  --limit N: 采前N个
"""
import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime

import pymysql
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9222"
DB_CONFIG = {"host": "localhost", "port": 3306, "user": "root", "password": "root123456", "database": "db_spzx", "charset": "utf8mb4"}
PROGRESS_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/collect_full_progress.json"
SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"
COOLDOWN = 1200
DELAY_MIN, DELAY_MAX = 15, 25


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            return set(json.load(open(PROGRESS_FILE)).get("done", []))
        except Exception:
            pass
    return set()


def save_progress(done):
    json.dump({"done": sorted(done)}, open(PROGRESS_FILE, "w"))


def load_products(limit, test):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    sql = "SELECT id, source_product_url, source_product_code FROM source_product WHERE is_deleted=0 AND source_product_url LIKE '%detail.1688.com/offer/%'"
    if test:
        sql += " LIMIT 3"
    elif limit:
        sql += f" LIMIT {limit}"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    out = []
    for pid, url, code in rows:
        m = re.search(r"offer/(\d+)", url or "")
        if m:
            out.append((pid, m.group(1), code))
    return out


async def fetch_one(page, offer_id):
    """一次详情页访问, 返回 {skus: [...], freight: float|None}"""
    captured = {}

    async def on_resp(r):
        if SKU_API in r.url:
            try:
                captured["body"] = await r.text()
            except Exception:
                pass

    page.on("response", lambda r: asyncio.create_task(on_resp(r)))

    url = f"https://detail.1688.com/offer/{offer_id}.html"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"    goto err: {str(e)[:50]}")
        return {"skus": [], "freight": None}

    await asyncio.sleep(random.uniform(2.5, 4))

    # 检测是否已下架(区分于风控): 下架商品无SKU且无运费, 但不该触发冷却
    delisted = False
    try:
        page_txt = await page.evaluate("() => document.body.innerText.slice(0, 200)")
        if "商品已下架" in page_txt or "已下架" in page_txt and "登录" not in page_txt and "验证" not in page_txt:
            delisted = True
    except Exception:
        pass

    # 提取 SKU
    skus = []
    if "body" in captured:
        try:
            data = json.loads(captured["body"])
            m = data.get("data", {}).get("skuSelectorBizModel", {})
            info = m.get("skuInfoMap", {})
            for key, sv in info.items():
                if not isinstance(sv, dict):
                    continue
                sku_key = key.replace("&gt;", ">")
                skus.append({
                    "sku_key": sku_key,
                    "sku_id": str(sv.get("skuId", "")),
                    "stock": int(sv.get("canBookCount", 0)),
                    "price": float(sv.get("price", 0)),
                    "spec_id": str(sv.get("specId", "")),
                })
        except Exception:
            pass

    # 提取运费
    freight = None
    for _ in range(2):
        try:
            m = await page.evaluate("""()=>{
                const t = document.body.innerText;
                const m = t.match(/运费¥\\s*([\\d.]+)\\s*起/);
                if (m) return parseFloat(m[1]);
                const m2 = t.match(/运费[:：]?\\s*¥?\\s*([\\d.]+)/);
                if (m2) return parseFloat(m2[1]);
                if (/免运费|包邮/.test(t)) return 0;
                return null;
            }""")
            freight = m
            break
        except Exception:
            await asyncio.sleep(2)

    # 提取销量(详情页"xxx人付款", 兜底"月销xxx件")
    sales = None
    try:
        t = await page.evaluate("() => document.body.innerText")
        m = re.search(r"([\d.]+)万?\+?人付款", t)
        if m:
            val = float(m.group(1))
            sales = int(val * 10000) if "万" in m.group(0) else int(val)
        else:
            m2 = re.search(r"月销([\d.]+)万?件", t)
            if m2:
                val = float(m2.group(1))
                sales = int(val * 10000) if "万" in m2.group(0) else int(val)
    except Exception:
        pass

    return {"skus": skus, "freight": freight, "delisted": delisted, "sales": sales}


def upsert_data(product_id, code, skus, freight, sales):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 存 SKU + 库存
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

    if skus:
        keys = [s["sku_key"] for s in skus]
        placeholders = ",".join(["%s"] * len(keys))
        cur.execute(
            f"UPDATE source_sku SET status=0, update_time=%s WHERE source_product_id=%s AND sku_key NOT IN ({placeholders}) AND is_deleted=0",
            [now, product_id] + keys,
        )

    # 存运费
    if freight is not None:
        cur.execute("UPDATE source_product SET freight_cost=%s WHERE id=%s", (freight, product_id))

    # 存销量快照
    if sales is not None:
        cur.execute(
            "INSERT INTO source_product_sales_history (source_product_id, sales_count, snapshot_time) VALUES (%s,%s,%s)",
            (product_id, sales, now),
        )

    conn.commit()
    cur.close()
    conn.close()


async def main():
    test = "--test" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    refresh = "--refresh" in sys.argv

    products = load_products(limit, test)
    log(f"待采集 {len(products)} 个 1688 商品")

    done = load_progress() if not refresh else set()
    todo = [(pid, oid, code) for pid, oid, code in products if refresh or str(pid) not in done]
    if test:
        todo = todo[:3]
    elif limit:
        todo = todo[:limit]
    log(f"本次采集 {len(todo)} 个 (跳过已完成 {len(products) - len(todo)})")

    async with async_playwright() as pw:
        b = await pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()

        ok = 0
        for i, (pid, offer_id, code) in enumerate(todo):
            result = await fetch_one(page, offer_id)
            skus = result["skus"]
            freight = result["freight"]
            delisted = result.get("delisted", False)
            sales = result.get("sales")

            if not skus and freight is None:
                if delisted:
                    log(f"  ⏭ {code} 商品已下架, 跳过(不冷却)")
                    done.add(str(pid))
                    save_progress(done)
                    continue
                log(f"  ✗ {code} 无SKU且无运费, 疑似风控, 冷却{COOLDOWN}s")
                await asyncio.sleep(COOLDOWN)
                result = await fetch_one(page, offer_id)
                skus = result["skus"]
                freight = result["freight"]
                delisted = result.get("delisted", False)
                sales = result.get("sales")
                if not skus and freight is None:
                    if delisted:
                        log(f"  ⏭ {code} 商品已下架, 跳过")
                    else:
                        log(f"  ✗ {code} 仍无数据, 跳过")
                    done.add(str(pid))
                    save_progress(done)
                    continue

            upsert_data(pid, code, skus, freight, sales)
            done.add(str(pid))
            save_progress(done)
            ok += 1

            sku_info = f"{len(skus)} SKU" if skus else "无SKU"
            freight_info = f"运费¥{freight}" if freight is not None else "无运费"
            sales_info = f"销量{sales}" if sales is not None else "无销量"
            log(f"  [{i+1}/{len(todo)}] {code} -> {sku_info}, {freight_info}, {sales_info}")

            if i < len(todo) - 1:
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

        await page.close()
        await b.close()

    log(f"完成: 成功 {ok}/{len(todo)}")


if __name__ == "__main__":
    asyncio.run(main())
