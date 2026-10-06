#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时探针: 4 个探路失败样本的当前错误态 dump (只读+开下拉, 不提交不存草稿)"""
import asyncio
import sys

from cdp_utils import connect_cdp
from assign_shop_category import log, wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"

DUMP_JS = """() => {
  const out = {board: '', errLines: [], skuHeaders: [], skuErrCols: {}, firstRowCells: []};
  const board = document.querySelector('#struct-error-board');
  out.board = board ? (board.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0, 600) : 'NO_BOARD';
  const lines = (document.body.innerText||'').split('\\n');
  for (const l of lines) {
    const t = l.trim();
    if (t && (t.includes('不能为空') || t.includes('必填') || t.includes('枚举') || t.includes('输入值'))) {
      out.errLines.push(t.slice(0, 120));
      if (out.errLines.length >= 25) break;
    }
  }
  const w = document.querySelector('#sell-field-sku');
  if (w) {
    const hs = [...w.querySelectorAll('.sell-sku-table-header-common-new')];
    out.skuHeaders = hs.map(e => (e.innerText||'').trim());
    const tr = w.querySelector('tr');
    if (tr) {
      [...tr.children].forEach((td, i) => {
        if ((td.id||'').includes('skuParam')) out.firstRowCells.push({i, id: td.id, hasErr: td.className.includes('has-error')});
      });
    }
    // 全表统计 has-error 单元格的列号
    const colErr = {};
    for (const tr of w.querySelectorAll('tr')) {
      [...tr.children].forEach((td, i) => {
        if ((td.id||'').includes('skuParam') && td.className.includes('has-error')) {
          const key = td.id.replace(/^\\d+-/, '');
          colErr[key] = (colErr[key]||0) + 1;
        }
      });
    }
    out.skuErrCols = colErr;
  }
  return out;
}"""

DUMP_CELL_JS = """(colIdx) => {
  const w = document.querySelector('#sell-field-sku');
  const tr = w && w.querySelector('tr');
  if (!tr) return null;
  const td = tr.children[colIdx];
  if (!td) return null;
  const sel = td.querySelector('span.next-select');
  return {
    id: td.id,
    cls: (td.className||'').slice(0, 120),
    selectCls: sel ? (sel.className||'').slice(0, 160) : null,
    text: (td.innerText||'').replace(/\\s+/g,' ').trim().slice(0, 60),
    html: td.innerHTML.slice(0, 900),
  };
}"""


async def main():
    ids = sys.argv[1].split(',')
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        for iid in ids:
            page = None
            try:
                page = await ctx.new_page()
                await page.goto(EDIT_URL.format(id=iid), timeout=60000, wait_until='domcontentloaded')
                title = await wait_edit_ready(page)
                log(f"==== {iid} | {title[:30]}")
                await scroll_edit_page(page)
                await asyncio.sleep(1)
                d = await page.evaluate(DUMP_JS)
                log(f"BOARD: {d['board'][:300]}")
                log(f"ERR_LINES: {d['errLines']}")
                log(f"SKU_HEADERS: {d['skuHeaders']}")
                log(f"SKU_ERR_COLS: {d['skuErrCols']}")
                log(f"FIRST_ROW_PARAM_CELLS: {d['firstRowCells']}")
                if len(sys.argv) > 2:
                    ci = int(sys.argv[2])
                    c = await page.evaluate(DUMP_CELL_JS, ci)
                    log(f"CELL[{ci}]: {c}")
            except Exception as e:
                log(f"{iid} ERR: {str(e)[:80]}")
            finally:
                if page is not None:
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    try:
                        await page.close()
                    except Exception:
                        pass
            await asyncio.sleep(2)
    finally:
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
