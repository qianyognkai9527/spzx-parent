#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_insight_body.py — 抓 triggerDynamicModule **完整**响应体，定位「手淘市场均价」的 JSON 路径。

背景：market_avg 页内换词路存在读表竞态（表格渲染慢于接口，读到上一个词的价）。
改从响应体直接解析价格可根除竞态。本探针做 1 次整页加载 + 3 次页内换词，
把全部数据模块完整 body 落 probe_body.json 供定位字段。
"""
import asyncio
import json
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import adjust_alimama_bid as akb  # noqa: E402  (复用 FILL_SEARCH_JS / CLICK_QUERY_JS)

PORT = 9222
WORDS = ["小香风外套", "琳琳皮草", "羊羔毛外套"]


async def main():
    log = lambda m: print(m, flush=True)
    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    page = await ctx.new_page()
    captured = []

    async def on_resp(r):
        if "triggerDynamicModule.json" not in r.url:
            return
        try:
            body = await r.text()
            post = r.request.post_data or ""
        except Exception:
            return
        captured.append({"url": r.url[:200], "post": post, "body": body})

    page.on("response", on_resp)

    w0 = quote(quote(WORDS[0]))
    url = f"https://one.alimama.com/index.html#!/insight/search/traffic-analysis/index?word={w0}"
    log(f"goto {url[:100]}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"goto 异常: {str(e)[:80]}")
    await asyncio.sleep(10)
    try:
        await page.evaluate(akb.CLICK_TAB_JS)
    except Exception:
        pass
    await asyncio.sleep(5)

    for w in WORDS:
        try:
            r = await akb._swap_and_query(page, w)
            log(f"换词 {w}: {r}")
        except Exception as e:
            log(f"换词 {w} 异常: {str(e)[:60]}")
        await asyncio.sleep(6)

    await page.close()
    out = os.path.join(os.path.dirname(__file__), "probe_body.json")
    with open(out, "w") as f:
        json.dump(captured, f, ensure_ascii=False, indent=1)
    log(f"捕获 {len(captured)} 个模块响应（完整 body）→ {out}")
    for c in captured:
        try:
            mid = json.loads(c["post"]).get("moduleId")
        except Exception:
            mid = "?"
        print(f"  moduleId={mid} bodyLen={len(c['body'])}")


asyncio.run(main())
