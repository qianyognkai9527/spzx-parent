#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读探测商品编辑页当前状态: 上架状态radio + 店铺分类tags. 绝不点击提交.
用法: venv/bin/python probe_item_state.py <itemId> [...]"""
import asyncio
import sys
import time
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def probe(ctx, item_id):
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), timeout=60000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page, timeout=40)
        if not title:
            return f"{item_id} | 加载失败"
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        state = await page.evaluate("""() => {
            const el = document.querySelector('#sell-field-startTime');
            if (!el) return 'NO_FIELD';
            for (const w of el.querySelectorAll('.next-radio-wrapper, .radio-item')) {
                const checked = w.getAttribute('aria-checked')==='true' || w.classList.contains('checked') || (w.querySelector('input')||{}).checked;
                if (checked) return (w.textContent||'').trim().slice(0, 20);
            }
            return 'NONE_SELECTED';
        }""")
        tags = await page.evaluate("""() => {
            const box = document.querySelector('#sell-field-shopcat');
            if (!box) return 'NO_FIELD';
            return Array.from(box.querySelectorAll('.next-tag')).map(t => t.textContent.trim());
        }""")
        return f"{item_id} | 上架状态={state} | 分类={tags} | {title[:20]}"
    except Exception as e:
        return f"{item_id} | ERR: {str(e)[:60]}"
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def main():
    ids = [a for a in sys.argv[1:] if a.isdigit()]
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        for iid in ids:
            log(await probe(ctx, iid))
            await asyncio.sleep(2)
    finally:
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
