#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读探测2: 全页表头 + 属性区空值下拉. 绝不提交."""
import asyncio
import json
import sys
import time
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main():
    iid = sys.argv[1]
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=iid), timeout=60000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page, timeout=40)
        log(f"标题: {title[:30] if title else 'LOAD_FAIL'}")
        await scroll_edit_page(page)
        await asyncio.sleep(1.5)
        # 1) 全页所有表 header
        ths = await page.evaluate(r'''() => {
            const seen = new Set();
            for (const t of document.querySelectorAll('table')) {
                const hs = [...t.querySelectorAll('th')].map(x => (x.innerText||'').trim().replace(/\n/g,'/')).filter(x=>x);
                if (hs.length) seen.add(hs.join(' | '));
            }
            return [...seen].slice(0, 10);
        }''')
        for h in ths:
            log("表头: " + h)
        # 2) SKU 表格首行单元格文本
        row0 = await page.evaluate(r'''() => {
            for (const t of document.querySelectorAll('table')) {
                const tr = t.querySelector('tbody tr');
                if (tr && /价格|库存/.test(t.innerText||'')) {
                    return [...tr.querySelectorAll('td')].map(td => (td.innerText||'').trim().replace(/\n/g,'/').slice(0,20));
                }
            }
            return null;
        }''')
        log("SKU首行: " + json.dumps(row0, ensure_ascii=False))
        # 3) 属性区(商品属性) 的下拉项: label -> 值(空标记)
        props = await page.evaluate(r'''() => {
            const out = [];
            // 找「商品属性」区块: 从含该文本的标题节点向下找 form items
            const all = [...document.querySelectorAll('*')];
            let zone = null;
            for (const el of all) {
                if (el.children.length === 0 && (el.textContent||'').trim() === '商品属性') { zone = el; break; }
            }
            if (!zone) return 'NO_ZONE';
            let box = zone.closest('[class*="field"], [class*="section"], [id*="prop"]') || zone.parentElement.parentElement;
            const items = box.querySelectorAll('.next-form-item, [class*="form-item"]');
            for (const it of items) {
                const label = it.querySelector('.next-form-item-label, [class*="label"]');
                const lt = label ? label.textContent.trim().replace(/\*/g,'').trim() : '';
                if (!lt || lt.length > 12) continue;
                const req = it.classList.contains('required') || !!it.querySelector('.next-required, [class*="required"]');
                const val = (it.querySelector('.next-select-value, .next-input input, .next-tag')||{}).textContent || '';
                out.push({label: lt.slice(0,12), req, val: (val||'').trim().slice(0,16)});
            }
            return out.slice(0, 30);
        }''')
        log("商品属性区: " + json.dumps(props, ensure_ascii=False))
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass
        try:
            from assign_shop_category_v2 import ensure_guard_tab
            ensure_guard_tab()
        except Exception:
            pass
        await b.close()


asyncio.run(main())
