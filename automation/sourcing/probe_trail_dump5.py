#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时探针5: 调试 detect_gaps 为何漏 提取方式 (S4 页面)"""
import asyncio
import json

from cdp_utils import connect_cdp
from assign_shop_category import log, wait_edit_ready, scroll_edit_page
from compliance_filler import clear_overlays, detect_gaps, parse_gaps

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id='1058428800598'), timeout=60000, wait_until='domcontentloaded')
        await wait_edit_ready(page)
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        st = await page.evaluate("""() => {
            const b = document.querySelector('#struct-error-board');
            const n = document.querySelectorAll('#struct-error-board').length;
            return {n: n, exists: !!b, display: b ? b.style.display : null,
                    visible: b ? b.getClientRects().length > 0 : null,
                    hasExtractInBody: (document.body.innerText||'').includes('提取方式')};
        }""")
        log(f"BEFORE clear_overlays: {json.dumps(st, ensure_ascii=False)}")
        log(f"detect BEFORE: {await detect_gaps(page)}")
        await clear_overlays(page)
        st2 = await page.evaluate("""() => {
            const b = document.querySelector('#struct-error-board');
            return {n: document.querySelectorAll('#struct-error-board').length,
                    display: b ? b.style.display : null,
                    hasExtractInBody: (document.body.innerText||'').includes('提取方式')};
        }""")
        log(f"AFTER clear_overlays: {json.dumps(st2, ensure_ascii=False)}")
        gaps = await detect_gaps(page)
        log(f"detect AFTER (hidden board): {gaps}")
        raw = await page.evaluate("""() => {
            const b = document.querySelector('#struct-error-board');
            if (!b) return 'NO_BOARD';
            const disp = b.style.display;
            b.style.display = '';
            const t = b.innerText || '';
            b.style.display = 'none';
            const lines = t.split('\\n').map(s => s.trim()).filter(Boolean);
            return {display: disp, lines: lines.slice(0, 25)};
        }""")
        log(f"board unhide-read: {json.dumps(raw, ensure_ascii=False)}")
        body2 = await page.evaluate("() => document.body.innerText")
        log(f"parse on body+board: {parse_gaps(body2 + chr(10) + chr(10).join(raw.get('lines', []) if isinstance(raw, dict) else []))}")
    except Exception as e:
        log(f"ERR: {str(e)[:120]}")
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
