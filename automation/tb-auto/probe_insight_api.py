#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_insight_api.py — 找出流量解析页背后返回「市场均价」的 XHR（只做一次页面加载）。

背景：pick_plan_keywords.py / adjust_alimama_bid.py 现在每个词都要 about:blank→goto
整页重载流量解析页，词多时几百次整页刷新，容易触发安全机制（2026-10-17 用户实测出现滑块）。
本探针只加载一次页面，捕获全部 alimama XHR，落 insight_probe.json 供人工定位接口。

用法: ./venv/bin/python tb-auto/probe_insight_api.py [--word 皮草外套]
"""
import argparse
import asyncio
import json
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222

CLICK_TAB_JS = r"""() => {
  const t=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
  const el=[...document.querySelectorAll('*')].find(e=>t(e)==='竞争流量透视');
  if(el){ el.click(); return true; } return false;
}"""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--word", default="皮草外套")
    args = ap.parse_args()
    log = lambda m: print(m, flush=True)
    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    page = await ctx.new_page()
    captured = []

    async def on_response(r):
        if "alimama.com" not in r.url:
            return
        try:
            body = await r.text()
        except Exception:
            body = ""
        captured.append({
            "url": r.url,
            "method": r.request.method,
            "status": r.status,
            "post": (r.request.post_data or "")[:800],
            "body": body[:30000],
        })

    page.on("response", on_response)

    w = quote(quote(args.word))  # 词双重 URL 编码
    url = f"https://one.alimama.com/index.html#!/insight/search/traffic-analysis/index?word={w}"
    log(f"goto {url[:110]}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"goto 异常: {str(e)[:80]}")
    await asyncio.sleep(10)

    try:
        clicked = await page.evaluate(CLICK_TAB_JS)
    except Exception as e:
        clicked = f"err {str(e)[:60]}"
    log(f"点击竞争流量透视: {clicked}")
    await asyncio.sleep(6)

    await page.close()

    out = os.path.join(os.path.dirname(__file__), "insight_probe.json")
    with open(out, "w") as f:
        json.dump({"word": args.word, "rows": captured}, f, ensure_ascii=False, indent=1)
    log(f"捕获 {len(captured)} 个 alimama 请求 → {out}")
    for r in captured:
        hit = ""
        low = r["body"]
        if "0.64" in low or '"marketPrice"' in low or "市场均价" in low or "avgPrice" in low:
            hit = "  <<< PRICE?"
        log(f"  [{r['method']} {r['status']}] {r['url'][:120]}{hit}")


asyncio.run(main())
