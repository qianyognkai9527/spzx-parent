#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重采当前淘宝仓库中(in_stock)/出售中(sold_out)全部商品ID+标题 -> 对应 jsonl
断点续跑: 已存在的条目跳过; 每页即时追加写文件(防进程被杀丢数据)。
用法: python collect_in_stock_current.py [--list in_stock|sold_out|both] [--limit N]
"""
import asyncio
import json
import os
import sys
import time
from playwright.async_api import async_playwright
from cdp_utils import connect_cdp

CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
URLS = {
    'in_stock': "https://myseller.taobao.com/home.htm/SellManage/in_stock?current=1&pageSize=20",
    'sold_out': "https://myseller.taobao.com/home.htm/SellManage/sold_out?current=1&pageSize=20",
}
OUT_FILES = {
    'in_stock': os.path.join(BASE, "taobao_in_stock_current.jsonl"),
    'sold_out': os.path.join(BASE, "taobao_onsale_current.jsonl"),
}
FIRST_URL = URLS['in_stock']   # 兼容旧引用
OUT = OUT_FILES['in_stock']    # 兼容旧引用


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


async def read_tab_count(page, name):
    """读列表 tab 计数(如 出售中(1840)/仓库中(2203)). 读不到返回 0(不设上限, 保持旧行为)"""
    pat = '出售中' if name == 'sold_out' else '仓库中'
    r = await page.evaluate("""(pat) => {
        const re = new RegExp(pat + '\\\\((\\\\d+)\\\\)');
        for (const el of document.querySelectorAll('.next-tabs-tab-inner')) {
            const m = (el.textContent||'').match(re);
            if (m) return parseInt(m[1], 10);
        }
        return 0;
    }""", pat)
    return int(r or 0)


def load_existing(out_path):
    seen = set()
    items = []
    if os.path.exists(out_path):
        for line in open(out_path, encoding='utf-8'):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    seen.add(r['itemId'])
                    items.append(r)
                except Exception:
                    pass
    return seen, items


def append_items(out_path, items):
    with open(out_path, 'a', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')


def parse_lists(argv):
    """argv(不含脚本名) -> (要采集的列表名列表, 剩余参数). --list both = 两个都采"""
    lists = ['in_stock']
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == '--list':
            val = argv[i + 1]
            assert val in ('in_stock', 'sold_out', 'both'), f'未知 --list {val}'
            lists = ['in_stock', 'sold_out'] if val == 'both' else [val]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return lists, rest


async def run_collect(name, limit, restart, b, ctx):
    out = OUT_FILES[name]
    first_url = URLS[name]

    seen, all_items = load_existing(out)
    log(f"[{name}] 已有 {len(seen)} 个, 断点续跑")

    page = None
    for p in ctx.pages:
        if f'SellManage/{name}' in p.url:
            page = p
            break
    if page is None:
        page = await ctx.new_page()
        await page.goto(first_url, wait_until='domcontentloaded', timeout=40000)
        await asyncio.sleep(12)
    elif restart:
        await page.goto(first_url, wait_until='domcontentloaded', timeout=40000)
        await asyncio.sleep(10)
    else:
        await page.bring_to_front()

    await close_overlays(page)
    await asyncio.sleep(2)

    # 页数上限: 读 tab 计数(出售中(N)/仓库中(N)), 防最后一页后「下一页」仍可点击越界采到其他状态商品 (2026-09-25 污染修复)
    tab_n = await read_tab_count(page, name)
    if tab_n > 0:
        max_pages = (tab_n + 19) // 20
        log(f"[{name}] tab计数={tab_n} -> 页数上限 {max_pages}")
    else:
        max_pages = 0
        log(f"[{name}] 未读到tab计数, 不设页数上限(保持旧行为)")

    pageno = 0
    try:
        while True:
            pageno += 1
            items = await extract_items(page)
            if not items:
                log(f"[{name}] 页{pageno}: 提取0个, 关闭弹窗重试...")
                await close_overlays(page)
                await asyncio.sleep(5)
                items = await extract_items(page)
                if not items:
                    log(f"[{name}] 页{pageno}: 仍为0, 结束")
                    break

            new_items = [it for it in items if it['itemId'] not in seen]
            all_items.extend(new_items)
            seen.update(it['itemId'] for it in new_items)
            append_items(out, new_items)
            log(f"[{name}] 页{pageno}: 本页{len(items)}个 新{len(new_items)}个 累计{len(all_items)}个")

            if limit and len(all_items) >= limit:
                all_items = all_items[:limit]
                break

            if max_pages and pageno >= max_pages:
                log(f"[{name}] 页{pageno}: 已达页数上限{max_pages}(tab计数{tab_n}), 停止翻页防越界")
                break

            ok = await click_next_page(page)
            if not ok:
                log(f"[{name}] 页{pageno}: 无下一页, 结束")
                break
            await asyncio.sleep(7)
            await close_overlays(page)
            await asyncio.sleep(1)
            if pageno > 250:
                log(f"[{name}] 超过250页安全限制, 结束")
                break
        log(f"[{name}] 完成: 共{len(all_items)}个商品 -> {out}")
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def main():
    lists, rest = parse_lists(sys.argv[1:])
    limit = 0
    if '--limit' in rest:
        limit = int(rest[rest.index('--limit') + 1])
    restart = '--restart' in rest

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com"], log=log)
    try:
        for name in lists:
            log(f"=== 采集列表 {name} ===")
            await run_collect(name, limit, restart, b, ctx)
    finally:
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
