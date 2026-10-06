#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控探测: 对已失败商品重放提交, 捕获错误高亮字段名. 只用于已 failed 商品(必再失败,无误存风险).
用法: venv/bin/python probe_field_names.py <itemId>...
前提: v2 运行已停止(勿在运行中并行)."""
import asyncio
import json
import sys
import time
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page, handle_recommend_dialog
from assign_shop_category_v2 import click_submit, ensure_guard_tab

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def dump_errors(page):
    return await page.evaluate(r'''() => {
        const out = {fields: [], skuCells: [], panel: ''};
        // 1) has-error / 错误样式包裹的 form-item -> label
        const seen = new Set();
        for (const it of document.querySelectorAll('.next-form-item, [class*="form-item"], [class*="field-item"]')) {
            const cls = it.className || '';
            if (!/has-error|error/i.test(String(cls))) continue;
            const label = it.querySelector('.next-form-item-label, [class*="label"]');
            const lt = label ? label.textContent.trim().replace(/\*/g,'').trim() : '';
            const fid = it.id || it.getAttribute('data-field') || '';
            const key = lt + '|' + fid;
            if (lt && !seen.has(key)) { seen.add(key); out.fields.push({label: lt.slice(0,24), id: fid.slice(0,40)}); }
        }
        // 2) SKU 表里错误标记的单元格: 表头名
        const w = document.getElementById('sell-field-sku');
        if (w) {
            for (const td of w.querySelectorAll('td')) {
                const tdCls = String(td.className||'');
                const inner = td.querySelector('[class*="error"], .next-input.has-error, [class*="has-error"]');
                if (/error/i.test(tdCls) || inner) {
                    const idx = td.cellIndex;
                    const row = td.closest('tr');
                    const table = row && row.closest('table');
                    let header = 'NO_HEADER';
                    if (table) {
                        const headRow = table.querySelector('thead tr') || table.querySelector('tr');
                        if (headRow && headRow.children[idx]) header = headRow.children[idx].innerText.trim().replace(/\n/g,'/');
                    }
                    const cellText = (td.innerText||'').trim().replace(/\n/g,'/').slice(0,30);
                    out.skuCells.push({header, cellText});
                }
            }
        }
        // 3) 优化建议面板
        const panel = [...document.querySelectorAll('*')].find(e => e.children.length===0 && (e.textContent||'').trim()==='优化建议');
        if (panel) {
            let box = panel.closest('[class*="dialog"], [class*="panel"], [class*="quality"]') || panel.parentElement;
            out.panel = (box.innerText||'').slice(0, 600);
        }
        return out;
    }''')


async def main():
    ids = [a for a in sys.argv[1:] if a.isdigit()]
    prog = json.load(open('shop_cat_v2_progress.json'))
    plan = {str(p['itemId']): p for p in json.load(open('shop_cat_plan.json'))}
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        for iid in ids:
            cat = plan.get(iid, {}).get('category', '?')
            in_failed = iid in prog['failed']
            log(f"=== {iid} 类目={cat} 在failed={in_failed}")
            if not in_failed:
                log("  跳过: 不在 failed(避免误存好商品)")
                continue
            page = None
            try:
                page = await ctx.new_page()
                await page.goto(EDIT_URL.format(id=iid), timeout=60000, wait_until='domcontentloaded')
                await wait_edit_ready(page, timeout=40)
                await scroll_edit_page(page)
                await asyncio.sleep(1)
                await handle_recommend_dialog(page)
                sok, smsg, risk = await click_submit(page)
                log(f"  提交判定: ok={sok} risk={risk} msg={smsg[:60]}")
                await asyncio.sleep(3)
                info = await dump_errors(page)
                log("  错误字段: " + json.dumps(info['fields'], ensure_ascii=False))
                log("  SKU错误列: " + json.dumps(info['skuCells'][:8], ensure_ascii=False))
                log("  面板: " + info['panel'][:200].replace('\n', ' | '))
            except Exception as e:
                log(f"  ERR: {str(e)[:80]}")
            finally:
                if page is not None:
                    try:
                        await page.close()
                    except Exception:
                        pass
                await asyncio.sleep(3)
    finally:
        ensure_guard_tab()
        await b.close()


asyncio.run(main())
