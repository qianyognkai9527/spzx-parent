#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISV「商品管理」采集: (淘宝 itemId, 1688 offerId) -> isv_offer_taobao_map.jsonl.
数据源(2026-10-01 用户指正): ISV「商品管理」表一行同时含 店铺商品ID(淘宝 itemId) 与
货源商品ID(1688 offerId) —— 不开新标签、无需点击。
前置: 9222 已登录 1688。
跑法:
  automation/venv/bin/python scrape_isv_offer_taobao.py --ids 1077395263073,1080310116827
  automation/venv/bin/python scrape_isv_offer_taobao.py            # 全量(994 条, 翻页)
"""
import argparse
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_utils import connect_cdp  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isv_offer_taobao_map.jsonl")
ISV_URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"

ROWS_JS = r"""() => {
  return [...document.querySelectorAll('tr')].map(tr => {
    const ids = [...(tr.innerText||'').matchAll(/ID：(\d+)/g)].map(m => m[1]);
    if (!ids.length) return null;
    const t = (tr.innerText||'').replace(/\s+/g,' ').trim();
    return {taobao_item_id: ids[0], offer_id: ids[1] || null, text: t};
  }).filter(Boolean);
}"""


async def get_frame(page):
    for _ in range(20):
        await asyncio.sleep(1)
        fr = [f for f in page.frames if "isv-container" in f.url]
        if fr:
            return fr[0]
    return None


async def open_page(ctx):
    for p in ctx.pages:
        if "fuwu_work_isv_container" in p.url:
            return p
    p = await ctx.new_page()
    await p.goto(ISV_URL, wait_until="domcontentloaded", timeout=40000)
    await asyncio.sleep(7)
    return p


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="", help="逗号分隔的店铺商品ID(淘宝 itemId), 精查")
    ap.add_argument("--keyword", default="甲")
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()

    b, ctx = await connect_cdp(9222, keep_urls=["fuwu_work_isv_container", "isv-container",
                                                "1688.com", "item.upload.taobao.com", "myseller.taobao.com"], log=print)
    page = await open_page(ctx)
    result = []
    try:
        fr = await get_frame(page)
        await fr.evaluate("""() => { const e=[...document.querySelectorAll('*')].find(x=>(x.children.length===0)&&(x.textContent||'').trim()==='商品管理'); if(e)e.click(); }""")
        await asyncio.sleep(6)
        if args.ids:
            await fr.locator("input#shopProductIds").fill(args.ids)
        else:
            # 清掉上次的筛选(SPA 会保留), 再按关键词搜
            for sel in ("input#shopProductIds", "input#sourceProductIds", "input#searchKey"):
                try:
                    await fr.locator(sel).fill("")
                except Exception:
                    pass
            await fr.locator("input#searchKey").fill(args.keyword)
        await fr.evaluate("""() => { const b=[...document.querySelectorAll('*')].find(x=>(x.children.length===0)&&(x.textContent||'').trim()==='查 询'); if(b)b.click(); }""")
        await asyncio.sleep(5)
        total = int((re.search(r"共\s*(\d+)\s*条", (await fr.inner_text("body"))).group(1) if re.search(r"共\s*(\d+)\s*条", (await fr.inner_text("body"))) else 0))
        pages = (total + 19) // 20 if total else 1
        print(f"命中 {total} 条, {pages} 页")
        for pg in range(1, pages + 1):
            if pg > 1:
                await fr.evaluate("""(p) => { const ns=[...document.querySelectorAll('[class*=pagination] *,[class*=Pagination] *')]; const e=ns.find(x=>(x.textContent||'').trim()===String(p)); if(e)e.click(); }""", pg)
                await asyncio.sleep(3)
            rows = await fr.evaluate(ROWS_JS)
            for r in rows:
                result.append({"taobao_item_id": r["taobao_item_id"], "offer_id": r["offer_id"],
                               "title": r["text"]})
                print(f"  {r['taobao_item_id']} -> {r['offer_id']}")
            if args.max and len(result) >= args.max:
                result = result[: args.max]
                break
            if total and pg * 20 >= total:
                break
        with open(OUT, "w", encoding="utf-8") as f:
            for r in result:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("WROTE", OUT, len(result), "含offerId:", sum(1 for r in result if r["offer_id"]))
    finally:
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
