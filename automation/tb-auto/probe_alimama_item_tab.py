#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_item_tab.py — 找"计划×日×宝贝"粒度到底走哪个 tab / 哪个接口.

背景: 光有计划日报答不了"这单是付费带来的还是免费流量带来的"。要的是宝贝粒度:
      每个计划每天在每个商品上花了多少、带来多少成交，才能和 order_info 对账。

上一轮我猜 sourceList=["campaign_detail"] + tab=word/crowd/item 全部无效(返回同一行汇总)。
真实列表页用的是 sourceList=["scene"] + tab="campaign"，所以这次**不猜**，
直接把每个 tab 的页面打开，录它自己发的请求和响应。

只读: 只 goto + 记录网络，不点按钮、不碰出价/预算/计划。
SPA 同 URL 改 query 不重渲染(已知坑) → 每个 tab 都新开一页。

跑法: automation/venv/bin/python probe_alimama_item_tab.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_alimama_out")
CAMPAIGN = "83392769388"
DAY = "2026-10-01"
TABS = ["item", "adgroup", "word", "crowd", "creative", "campaign"]
URL = ("https://one.alimama.com/index.html#!/manage/search-detail?mx_bizCode=onebpSearch"
       "&bizCode=onebpSearch&tab={tab}&startTime={d}&endTime={d}&campaignId=" + CAMPAIGN)
# 实体标识候选：只要响应行里出现这些键之一，说明这维度真的下钻到了明细
ENTITY_KEYS = ("itemId", "itemName", "adgroupId", "adgroupName", "word", "wordId",
               "crowdId", "crowdName", "creativeId", "creativeName", "promotionName",
               "materialId", "entityId", "campaignId", "campaignName")


def log(m):
    print(m, flush=True)


async def probe_tab(ctx, tab):
    page = await ctx.new_page()
    seen = []

    async def on_resp(resp):
        u = resp.url
        if "alimama" not in u or ".json" not in u:
            return
        if not any(k in u for k in ("report/query", "findPage", "findList", "query.json")):
            return
        try:
            body = await resp.text()
            j = json.loads(body)
        except Exception:
            return
        data = j.get("data") or {}
        lst = data.get("list") if isinstance(data, dict) else None
        if not isinstance(lst, list):
            return
        try:
            post = resp.request.post_data
        except Exception:
            post = None
        seen.append({"url": u.split("?")[0], "n": len(lst), "size": len(body),
                     "keys": sorted(lst[0].keys()) if lst and isinstance(lst[0], dict) else [],
                     "row": lst[0] if lst and isinstance(lst[0], dict) else None,
                     "post": post})

    page.on("response", on_resp)
    try:
        await page.goto(URL.format(tab=tab, d=DAY), wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log(f"  goto 异常: {str(e)[:60]}")
    await asyncio.sleep(16)
    await page.close()

    hit = [s for s in seen if s["n"] > 0]
    log(f"\n### tab={tab}  有数据的接口 {len(hit)} 个")
    for s in sorted(hit, key=lambda x: -x["n"]):
        ents = [k for k in ENTITY_KEYS if k in s["keys"]]
        log(f"  n={s['n']:>4} {s['size']:>8}B {s['url'].split('one.alimama.com/')[-1][:58]}"
            f"  实体键={','.join(ents) or '无'}")
        if s["post"]:
            try:
                b = json.loads(s["post"])
                log(f"       请求: tab={b.get('tab')} sourceList={b.get('sourceList')} "
                    f"queryDomains={b.get('queryDomains')} rptQuery={'有' if b.get('rptQuery') else '无'}")
            except Exception:
                pass
        if s["row"] and any(k in s["row"] for k in ("itemId", "itemName", "word", "adgroupName")):
            r = s["row"]
            want = ("itemId", "itemName", "word", "adgroupName", "crowdName",
                    "charge", "alipayInshopAmt", "click", "promotionName")
            sample = {k: v for k, v in r.items() if k in want}
            log("       首行: " + json.dumps(sample, ensure_ascii=False)[:230])
    fn = os.path.join(OUT, f"tab_{tab}.json")
    open(fn, "w", encoding="utf-8").write(json.dumps(
        [{"url": s["url"], "n": s["n"], "keys": s["keys"], "post": s["post"], "row": s["row"]}
         for s in hit], ensure_ascii=False, indent=1))
    return hit


async def main():
    os.makedirs(OUT, exist_ok=True)
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    summary = {}
    for tab in TABS:
        hits = await probe_tab(ctx, tab)
        summary[tab] = max([h["n"] for h in hits], default=0)
        await asyncio.sleep(3)
    log("\n=== 汇总: 每个 tab 能拿到的最大行数 ===")
    for k, v in summary.items():
        log(f"  tab={k:<9} 最多 {v} 行")
    log("\n明细见 probe_alimama_out/tab_<tab>.json")
    await b.close()


if __name__ == "__main__":
    asyncio.run(main())
