#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时探针2: 款式/图案 SKU 单元格控件结构 + 下拉选项 dump (只读, Escape 关闭, 不提交)"""
import asyncio
import sys

from cdp_utils import connect_cdp
from assign_shop_category import log, wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"

CELL_JS = """(colIdx) => {
  const w = document.querySelector('#sell-field-sku');
  const tr = w && w.querySelector('tr');
  if (!tr) return null;
  const td = tr.children[colIdx];
  if (!td) return null;
  const sel = td.querySelector('span.next-select');
  const inp = td.querySelector('input');
  return {
    id: td.id,
    selectCls: sel ? sel.className : null,
    text: (td.innerText||'').replace(/\\s+/g,' ').trim().slice(0, 80),
    inputPh: inp ? inp.placeholder : null,
    inputVal: inp ? inp.value : null,
    html: td.innerHTML.slice(0, 1200),
  };
}"""

ALL_ROWS_CELL_TEXT = """(colIdx) => {
  const w = document.querySelector('#sell-field-sku');
  const out = [];
  for (const tr of w.querySelectorAll('tr')) {
    const td = tr.children[colIdx];
    if (!td) continue;
    out.push({rowId: td.id, hasErr: td.className.includes('has-error'),
              text: (td.innerText||'').replace(/\\s+/g,' ').trim().slice(0, 40)});
  }
  return out;
}"""


async def dump_cell(page, iid, col, name):
    c = await page.evaluate(CELL_JS, col)
    log(f"[{iid}] {name} cell: selectCls={c and c['selectCls']}")
    log(f"[{iid}] {name} text={c and c['text']!r} inputPh={c and c['inputPh']!r} inputVal={c and c['inputVal']!r}")
    log(f"[{iid}] {name} html: {c and c['html']}")
    rows = await page.evaluate(ALL_ROWS_CELL_TEXT, col)
    log(f"[{iid}] {name} all rows: {rows}")
    # 点开下拉看选项 (read-only)
    if c and c.get('selectCls'):
        try:
            trig = page.locator(f'#sell-field-sku [id="{c["id"]}"] span.next-select').first
            await trig.click(timeout=6000)
            await asyncio.sleep(1.2)
            opts = await page.evaluate("""() => {
                const wraps = [...document.querySelectorAll('.next-overlay-wrapper.opened')];
                if (!wraps.length) return 'NO_POPUP';
                const w = wraps[wraps.length - 1];
                return [...w.querySelectorAll('.options-item')]
                    .map(e => e.getAttribute('title') || (e.innerText||'').trim()).filter(Boolean).slice(0, 40);
            }""")
            log(f"[{iid}] {name} options: {opts}")
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
        except Exception as e:
            log(f"[{iid}] {name} dropdown ERR: {str(e)[:60]}")
            try:
                await page.keyboard.press('Escape')
            except Exception:
                pass


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        # 样本1: 款式 = col 6
        page = None
        try:
            page = await ctx.new_page()
            await page.goto(EDIT_URL.format(id='1078910949614'), timeout=60000, wait_until='domcontentloaded')
            await wait_edit_ready(page)
            await scroll_edit_page(page)
            await asyncio.sleep(1)
            await dump_cell(page, '1078910949614', 6, '款式')
        except Exception as e:
            log(f"样本1 ERR: {str(e)[:80]}")
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
        await asyncio.sleep(2)
        # 样本2: 图案 = col 9
        page = None
        try:
            page = await ctx.new_page()
            await page.goto(EDIT_URL.format(id='888970440898'), timeout=60000, wait_until='domcontentloaded')
            await wait_edit_ready(page)
            await scroll_edit_page(page)
            await asyncio.sleep(1)
            await dump_cell(page, '888970440898', 9, '图案')
        except Exception as e:
            log(f"样本2 ERR: {str(e)[:80]}")
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
    finally:
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
