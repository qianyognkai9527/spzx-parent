#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重采当前淘宝仓库中(in_stock)全部商品ID+标题 -> taobao_in_stock_current.jsonl
断点续跑: 已存在的条目跳过; 每页即时追加写文件(防进程被杀丢数据)。
用法: python collect_in_stock_current.py [--limit N]
"""
import asyncio
import json
import os
import sys
import time
from playwright.async_api import async_playwright
from cdp_utils import connect_cdp

CDP_PORT = 9222
FIRST_URL = "https://myseller.taobao.com/home.htm/SellManage/in_stock?current=1&pageSize=20"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taobao_in_stock_current.jsonl")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def close_overlays(page):
    await page.evaluate(r'''() => {
        for (const e of document.querySelectorAll('*')) {
            const t = (e.textContent||'').trim();
            if (e.children.length === 0 && (t === '我知道了' || t === '忽略' || t === '去优化' || t === '暂不')) { try { e.click(); } catch(x) {} }
        }
        for (const c of document.querySelectorAll('.next-icon-close_blod, .next-dialog-close')) { try { c.click(); } catch(x) {} }
    }''')


async def extract_items(page):
    return await page.evaluate(r'''() => {
        const rows = [...document.querySelectorAll('tr.next-table-row')];
        const out = [];
        for (const row of rows) {
            const txt = row.innerText || '';
            const m = txt.match(/ID:(\d+)/);
            const link = row.querySelector('a.title-link');
            if (m && link) out.push({itemId: m[1], title: link.textContent.trim().slice(0, 100)});
        }
        return out;
    }''')


async def click_next_page(page):
    ok = await page.evaluate(r'''() => {
        const btns = [...document.querySelectorAll('button')];
        for (const b of btns) {
            const t = (b.textContent||'').trim();
            const r = b.getBoundingClientRect();
            if (t === '下一页' && r.width > 10 && r.height > 5 && !b.disabled) {
                b.click();
                return true;
            }
        }
        return false;
    }''')
    return bool(ok)


def load_existing():
    seen = set()
    items = []
    if os.path.exists(OUT):
        for line in open(OUT, encoding='utf-8'):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    seen.add(r['itemId'])
                    items.append(r)
                except Exception:
                    pass
    return seen, items


def append_items(items):
    with open(OUT, 'a', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')


async def main():
    limit = 0
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    restart = '--restart' in sys.argv

    seen, all_items = load_existing()
    log(f"已有 {len(seen)} 个, 断点续跑")

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com"], log=log)

    page = None
    for p in ctx.pages:
        if 'SellManage/in_stock' in p.url:
            page = p
            break
    if page is None:
        page = await ctx.new_page()
        await page.goto(FIRST_URL, wait_until='domcontentloaded', timeout=40000)
        await asyncio.sleep(12)
    elif restart:
        await page.goto(FIRST_URL, wait_until='domcontentloaded', timeout=40000)
        await asyncio.sleep(10)
    else:
        await page.bring_to_front()

    await close_overlays(page)
    await asyncio.sleep(2)

    pageno = 0
    try:
        while True:
            pageno += 1
            items = await extract_items(page)
            if not items:
                log(f"页{pageno}: 提取0个, 关闭弹窗重试...")
                await close_overlays(page)
                await asyncio.sleep(5)
                items = await extract_items(page)
                if not items:
                    log(f"页{pageno}: 仍为0, 结束")
                    break

            new_items = [it for it in items if it['itemId'] not in seen]
            all_items.extend(new_items)
            seen.update(it['itemId'] for it in new_items)
            append_items(new_items)
            log(f"页{pageno}: 本页{len(items)}个 新{len(new_items)}个 累计{len(all_items)}个")

            if limit and len(all_items) >= limit:
                all_items = all_items[:limit]
                break

            ok = await click_next_page(page)
            if not ok:
                log(f"页{pageno}: 无下一页, 结束")
                break
            await asyncio.sleep(7)
            await close_overlays(page)
            await asyncio.sleep(1)
            if pageno > 250:
                log("超过250页安全限制, 结束")
                break
        log(f"完成: 共{len(all_items)}个商品 -> {OUT}")
    finally:
        try:
            await page.close()
        except Exception:
            pass
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
