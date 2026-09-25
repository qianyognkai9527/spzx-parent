#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读 dump 合规相关控件结构 -> compliance_ui_notes.md. 绝不提交."""
import asyncio
import sys
import time
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page
from compliance_filler import clear_overlays

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


DUMP_JS = r'''() => {
    const out = {};
    // A) SKU「去填写」按钮上下文
    const w = document.getElementById('sell-field-sku');
    if (w) {
        const btn = [...w.querySelectorAll('button, a, span, td')].find(e => (e.textContent||'').trim() === '去填写');
        out.qtf = btn ? {tag: btn.tagName, cls: String(btn.className).slice(0,80),
                         inZone: !!btn.closest('#sell-field-sku')} : null;
    }
    // B) 属性区: 面料/材质成分控件
    const matBtn = [...document.querySelectorAll('button, a, span, div')]
        .find(e => e.children.length === 0 && (e.textContent||'').trim() === '添加材质成分');
    out.matBtn = matBtn ? {tag: matBtn.tagName, cls: String(matBtn.className).slice(0,80)} : null;
    // C) 属性区各 select/radio 控件: label -> 组件类型
    out.attrs = [];
    for (const it of document.querySelectorAll('.next-form-item')) {
        const label = it.querySelector('.next-form-item-label');
        const lt = label ? label.textContent.trim().replace(/\*/g,'').trim() : '';
        if (!lt || lt.length > 10) continue;
        const comp = it.querySelector('.next-select, .next-radio-group, .next-checkbox-wrapper, .next-cascader, .next-input, textarea, [class*="material"]');
        out.attrs.push({label: lt, req: it.classList.contains('required'),
                        comp: comp ? (comp.className||'').toString().split(' ').slice(0,3).join(' ') : 'NONE'});
    }
    return out;
}'''


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    lines = ["# 合规控件结构发现 (自动生成 %s)\n" % time.strftime('%Y-%m-%d %H:%M')]
    try:
        for iid in sys.argv[1:]:
            if not iid.isdigit():
                continue
            page = await ctx.new_page()
            try:
                await page.goto(EDIT_URL.format(id=iid), timeout=60000, wait_until='domcontentloaded')
                title = await wait_edit_ready(page, timeout=40)
                if not title:
                    log(f"{iid} LOAD_FAIL"); continue
                await scroll_edit_page(page)
                await asyncio.sleep(1.5)
                await clear_overlays(page)
                info = await page.evaluate(DUMP_JS)
                lines.append(f"## {iid}\n```json\n{json.dumps(info, ensure_ascii=False, indent=1)}\n```\n")
                log(f"{iid}: qtf={bool(info.get('qtf'))} matBtn={bool(info.get('matBtn'))} attrs={len(info.get('attrs', []))}")
            except Exception as e:
                log(f"{iid} ERR {str(e)[:60]}")
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                await asyncio.sleep(2)
    finally:
        from assign_shop_category_v2 import ensure_guard_tab
        ensure_guard_tab()
        await b.close()
    with open('compliance_ui_notes.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    log("-> compliance_ui_notes.md")


import json
asyncio.run(main())
