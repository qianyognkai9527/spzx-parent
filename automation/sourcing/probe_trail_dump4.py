#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时探针4: 判定 #struct-error-board 是否随表单填写实时更新
S1 全部 12 行款式 填充(真实点击, 页面关闭即弃不保存) → 前后对比 board 文本"""
import asyncio

from cdp_utils import connect_cdp
from assign_shop_category import log, wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"

BOARD_JS = """() => {
  const b = document.querySelector('#struct-error-board');
  if (!b) return 'NO_BOARD';
  const t = b.innerText || '';
  const m = t.match(/错误\\s*\\(?(\\d+)\\)?/);
  const sku = t.match(/销售信息\\s*(\\d+)/);
  const ext = /提取方式\\s*必填/.test(t);
  return {errCount: m ? m[1] : null, skuCount: sku ? sku[1] : null, extractErr: ext,
          visible: b.getClientRects().length > 0, head: t.replace(/\\s+/g,' ').slice(0, 120)};
}"""

MSG_BAR_JS = """() => {
  const w = document.querySelector('#sell-field-sku');
  if (!w) return null;
  const mb = w.querySelector('.msg-bar .next-message');
  return mb ? (mb.innerText||'').replace(/\\s+/g,' ').trim().slice(0, 80) : 'NO_MSGBAR';
}"""


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id='1078910949614'), timeout=60000, wait_until='domcontentloaded')
        await wait_edit_ready(page)
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        log(f"BEFORE board: {await page.evaluate(BOARD_JS)}")
        log(f"BEFORE msgbar: {await page.evaluate(MSG_BAR_JS)}")
        filled = 0
        for i in range(12):
            cid = f'{i}-skuParam_p-657638213'
            try:
                trig = page.locator(f'#sell-field-sku [id="{cid}"] span.next-select').first
                if await trig.count() == 0:
                    log(f"row{i}: NO_TRIGGER")
                    continue
                await trig.click(timeout=8000)
                opt = None
                for _ in range(8):
                    await asyncio.sleep(0.5)
                    if await page.locator('.next-overlay-wrapper.opened .options-item[title="印花"]').count() > 0:
                        opt = page.locator('.next-overlay-wrapper.opened .options-item[title="印花"]').last
                        break
                if opt is None:
                    log(f"row{i}: NO_OPTIONS")
                    await page.keyboard.press('Escape')
                    continue
                await opt.click(timeout=6000)
                await asyncio.sleep(0.6)
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.4)
                t = await page.evaluate(f"""() => {{
                    const td = document.getElementById('{cid}');
                    return td ? (td.innerText||'').replace(/\\s+/g,' ').trim() : 'NO_TD';
                }}""")
                filled += 1 if '印花' in t else 0
                log(f"row{i}: written={t!r}")
            except Exception as e:
                log(f"row{i}: ERR {str(e)[:60]}")
                try:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.4)
                except Exception:
                    pass
        log(f"filled={filled}/12")
        log(f"AFTER board: {await page.evaluate(BOARD_JS)}")
        log(f"AFTER msgbar: {await page.evaluate(MSG_BAR_JS)}")
    except Exception as e:
        log(f"ERR: {str(e)[:100]}")
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
