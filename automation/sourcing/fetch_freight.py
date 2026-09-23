"""补抓已落库商品的1688详情页运费,写入 source_product.freight_cost。
用法: python fetch_freight.py [--limit N] [--test]
抗风控: 页间延迟 + 0卡/异常自动冷却重试 + 进度断点(已完成跳过)
"""
import asyncio
import json
import os
import random
import re
import time
import pymysql
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9223"
DB = {"host": "localhost", "port": 3306, "user": "root", "password": "root123456", "database": "db_spzx", "charset": "utf8mb4"}
PROGRESS_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/freight_progress.json"
COOLDOWN = 1200  # 触发风控冷却秒数 (20分钟, 减少反复风控)
MAX_RETRY = 1
DELAY_MIN, DELAY_MAX = 15, 25


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            return set(json.load(open(PROGRESS_FILE)).get("done", []))
        except Exception:
            pass
    return set()


def save_progress(done):
    json.dump({"done": sorted(done)}, open(PROGRESS_FILE, "w"))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def fetch_one(page, url):
    """返回运费数字(float)或 None"""
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=45000)
    except Exception as e:
        log(f"    goto err: {str(e)[:50]}")
        return None
    await asyncio.sleep(random.uniform(2.5, 4))
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
            return m
        except Exception:
            await asyncio.sleep(2)
    return None


async def main():
    args = None
    test = '--test' in __import__('sys').argv
    limit = 0
    if '--limit' in __import__('sys').argv:
        i = __import__('sys').argv.index('--limit')
        limit = int(__import__('sys').argv[i + 1])

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    # 只抓还没填运费的
    cur.execute("SELECT id, source_product_code, source_product_url FROM source_product WHERE is_deleted=0 AND (freight_cost IS NULL)")
    rows = cur.fetchall()
    cur.close(); conn.close()
    log(f"待抓运费: {len(rows)} 条")

    done = load_progress()
    to_fetch = [r for r in rows if str(r[0]) not in done]
    if test:
        to_fetch = to_fetch[:1]
    elif limit:
        to_fetch = to_fetch[:limit]
    log(f"本次抓取: {len(to_fetch)} 条")

    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        updated = 0
        for i, (pid, code, url) in enumerate(to_fetch):
            url = url or f"https://detail.1688.com/offer/{code}.html"
            freight = await fetch_one(page, url)
            if freight is None:
                # 可能是风控/页面异常,冷却重试一次
                log(f"  第{i+1} 条 {code} 未抓到运费,疑似风控,冷却{COOLDOWN}s重试")
                await asyncio.sleep(COOLDOWN)
                freight = await fetch_one(page, url)
                if freight is None:
                    log(f"  ✗ {code} 仍无运费,跳过")
                    done.add(str(pid)); save_progress(done)
                    continue
            conn2 = pymysql.connect(**DB)
            cur2 = conn2.cursor()
            cur2.execute("UPDATE source_product SET freight_cost=%s WHERE id=%s", (freight, pid))
            conn2.commit(); cur2.close(); conn2.close()
            updated += 1
            done.add(str(pid)); save_progress(done)
            log(f"  ✓ {code} 运费¥{freight} ({i+1}/{len(to_fetch)})")
            if i < len(to_fetch) - 1:
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        log(f"完成,共更新 {updated} 条")
        await page.close()
        await b.close()

asyncio.run(main())
