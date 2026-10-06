#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读探测: 编辑页中 被标必填但未填 的字段(规格/属性区). 绝不提交."""
import asyncio
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
        # 找 required 标记且值为空的表单项: .next-form-item.required / aria-required
        info = await page.evaluate(r'''() => {
            const out = {attrFields: [], skuFields: []};
            // 1) 所有带 required 标记的 form-item
            const items = document.querySelectorAll('.next-form-item, .sell-form-item, [class*="form-item"]');
            for (const it of items) {
                const label = it.querySelector('.next-form-item-label, [class*="label"]');
                const lt = label ? label.textContent.trim().replace(/[\*必填]/g,'').trim() : '';
                const required = it.classList.contains('required') || it.querySelector('.next-required, [class*="required"]') != null;
                if (!required || !lt) continue;
                // 值是否为空: 输入框/无选中 tag
                const inputs = it.querySelectorAll('input, textarea');
                let hasVal = false;
                for (const inp of inputs) { if ((inp.value||'').trim()) { hasVal = true; break; } }
                const tags = it.querySelectorAll('.next-tag, .next-select-value');
                for (const t of tags) { if ((t.textContent||'').trim()) { hasVal = true; break; } }
                // 所在区域判断: sku/规格 区 vs 属性区
                const zone = it.closest('#sell-field-sku, [id*="sku"], [id*="SKU"]') ? 'sku'
                           : (it.closest('#sell-field-props, [id*="prop"]') ? 'prop' : 'other');
                const rec = {label: lt.slice(0,30), zone, filled: hasVal};
                if (zone === 'sku') out.skuFields.push(rec);
                else if (zone === 'prop') out.attrFields.push(rec);
                else out.attrFields.push(rec);
            }
            return out;
        }''')
        log("属性区 required 项: " + json.dumps(info['attrFields'], ensure_ascii=False))
        log("SKU/规格区 required 项: " + json.dumps(info['skuFields'], ensure_ascii=False))
        # SKU 表头结构
        sku_hdr = await page.evaluate(r'''() => {
            const t = document.querySelector('#sell-field-sku, [id*="sell-field-sku"]');
            if (!t) return 'NO_SKU_FIELD';
            const ths = [...t.querySelectorAll('th')].map(x => (x.innerText||'').trim().replace(/\n/g,''));
            return ths.filter(x=>x);
        }''')
        log("SKU 表头: " + json.dumps(sku_hdr, ensure_ascii=False))
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass
        try:
            import assign_shop_category_v2 as v2
            v2.ensure_guard_tab()
        except Exception:
            pass
        await b.close()


import json
asyncio.run(main())
