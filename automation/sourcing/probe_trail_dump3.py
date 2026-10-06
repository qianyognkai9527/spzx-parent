#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时探针3: 实弹微实验 (页面关闭即弃, 不提交不存草稿)
1) 样本1 行0 款式: 点trigger→等popup→点选项→dump写回态  (复现 fill_sku_gaps 行为)
2) 样本2 行0 图案: 开popup dump 已选中项 (找隐藏的非法枚举值)
3) 样本4 行0 裤型/裤长: 开popup dump 选项确认可填
"""
import asyncio

from cdp_utils import connect_cdp
from assign_shop_category import log, wait_edit_ready, scroll_edit_page

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"

POPUP_OPTS_JS = """() => {
  const wraps = [...document.querySelectorAll('.next-overlay-wrapper.opened')];
  if (!wraps.length) return null;
  const w = wraps[wraps.length - 1];
  return [...w.querySelectorAll('.options-item')].map(e => ({
    title: e.getAttribute('title') || (e.innerText||'').trim(),
    cls: (e.className||'').includes('selected') ? 'SEL' : '',
  })).slice(0, 40);
}"""

TRIGGER_TEXT_JS = """(cellId) => {
  const td = document.getElementById(cellId);
  if (!td) return 'NO_TD';
  const tags = [...td.querySelectorAll('.next-tag-body')].map(e => (e.innerText||'').trim());
  const sel = td.querySelector('span.next-select');
  return JSON.stringify({innerText: (sel ? sel.innerText : '').replace(/\\s+/g,' ').trim(),
                         tags: tags, compact: (td.querySelector('.next-select-tag-compact')||{}).innerText || ''});
}"""


async def open_and_dump(page, cell_id, label, do_pick=None):
    trig = page.locator(f'#sell-field-sku [id="{cell_id}"] span.next-select').first
    await trig.click(timeout=8000)
    opts = None
    for _ in range(8):   # async-select: popup 可能延迟出现, 轮询 0.5s x8
        await asyncio.sleep(0.5)
        opts = await page.evaluate(POPUP_OPTS_JS)
        if opts:
            break
    log(f"[{label}] options({len(opts) if opts else 0}): {opts}")
    if do_pick and opts:
        titles = [o['title'] for o in opts]
        if do_pick in titles:
            opt = page.locator('.next-overlay-wrapper.opened .options-item[title="' + do_pick + '"]').last
            await opt.click(timeout=6000)
            await asyncio.sleep(1.0)
            t = await page.evaluate(TRIGGER_TEXT_JS, cell_id)
            log(f"[{label}] after pick {do_pick!r} trigger: {t}")
        else:
            log(f"[{label}] pick {do_pick!r} not in options")
    await page.keyboard.press('Escape')
    await asyncio.sleep(0.6)
    # Escape 后再读一次写回态 (popup 关闭后 trigger 真实文本)
    t2 = await page.evaluate(TRIGGER_TEXT_JS, cell_id)
    log(f"[{label}] after escape trigger: {t2}")


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        # 1) 样本1 行0 款式 实弹选值
        page = None
        try:
            page = await ctx.new_page()
            await page.goto(EDIT_URL.format(id='1078910949614'), timeout=60000, wait_until='domcontentloaded')
            await wait_edit_ready(page)
            await scroll_edit_page(page)
            await asyncio.sleep(1)
            await open_and_dump(page, '0-skuParam_p-657638213', 'S1款式row0', do_pick='印花')
        except Exception as e:
            log(f"S1 ERR: {str(e)[:100]}")
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
        await asyncio.sleep(2)
        # 2) 样本2 行0 图案 已选值
        page = None
        try:
            page = await ctx.new_page()
            await page.goto(EDIT_URL.format(id='888970440898'), timeout=60000, wait_until='domcontentloaded')
            await wait_edit_ready(page)
            await scroll_edit_page(page)
            await asyncio.sleep(1)
            t = await page.evaluate(TRIGGER_TEXT_JS, '0-skuParam_p-20603')
            log(f"[S2图案row0] closed-state: {t}")
            await open_and_dump(page, '0-skuParam_p-20603', 'S2图案row0')
        except Exception as e:
            log(f"S2 ERR: {str(e)[:100]}")
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
        await asyncio.sleep(2)
        # 3) 样本4 行0 裤型/裤长 选项
        page = None
        try:
            page = await ctx.new_page()
            await page.goto(EDIT_URL.format(id='1058428800598'), timeout=60000, wait_until='domcontentloaded')
            await wait_edit_ready(page)
            await scroll_edit_page(page)
            await asyncio.sleep(1)
            await open_and_dump(page, '0-skuParam_p-122276315', 'S4裤型row0')
            await open_and_dump(page, '0-skuParam_p-122276111', 'S4裤长row0')
        except Exception as e:
            log(f"S4 ERR: {str(e)[:100]}")
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
