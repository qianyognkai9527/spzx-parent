#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_manage.py — 录阿里妈妈两个推广产品「计划列表页」的数据接口.

目的: 报表页的 report/query.json 只认单个 campaignId, 拿不到"所有标准计划"。
      计划列表页本来就是跨计划聚合的, 它调什么接口、带不带指标, 决定了采集能不能一次拿全。

只读: 只 goto 列表页 + 记录网络请求, 不点按钮、不碰出价/预算/计划开关。

跑法: automation/venv/bin/python probe_alimama_manage.py
产物: probe_alimama_out/manage_<页面>_<序号>_<接口>.json + manage_index.txt
"""
import asyncio
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_alimama_out")
PAGES = [
    ("search", "https://one.alimama.com/index.html#!/manage/search?mx_bizCode=onebpSearch"
               "&bizCode=onebpSearch&startTime=2026-10-01&endTime=2026-10-01"),
    ("display", "https://one.alimama.com/index.html#!/manage/display?mx_bizCode=onebpDisplay"
                "&bizCode=onebpDisplay&startTime=2026-10-01&endTime=2026-10-01"),
]
SKIP_HOST = ("g.alicdn.com", "mmstat.com", "fourier.taobao.com", "alicdn.com",
             "emogine.insights", "ai.alimama.com", "insights.1688.com")
# 只关心"像数据接口"的: 这些词命中的才存正文
HINT = ("findPage", "findList", "query", "report", "horizontal", "list", "get", "page", "search")


def log(m):
    print(m, flush=True)


def tag_of(url):
    path = url.split("?")[0].split("//")[-1]
    return re.sub(r"[^a-zA-Z0-9]+", "_", path)[:60]


async def run_page(ctx, tag, url, wait):
    page = await ctx.new_page()
    rows = []

    async def on_resp(resp):
        u = resp.url
        host = u.split("//")[-1].split("/")[0] if "//" in u else ""
        if any(s in host for s in SKIP_HOST):
            return
        if "alimama" not in host and "taobao" not in host:
            return
        if not any(h in u.lower() for h in HINT):
            return
        ct = (resp.headers or {}).get("content-type", "")
        if "json" not in ct:
            return
        try:
            body = await resp.text()
        except Exception:
            return
        try:
            j = json.loads(body)
        except Exception:
            return
        data = j.get("data")
        n, keys = -1, []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    n = len(v)
                    if v and isinstance(v[0], dict):
                        keys = sorted(v[0].keys())
                    break
            if n < 0 and data:
                keys = sorted(data.keys())[:12]
        elif isinstance(data, list):
            n = len(data)
            if data and isinstance(data[0], dict):
                keys = sorted(data[0].keys())
        try:
            post = resp.request.post_data
        except Exception:
            post = None
        rows.append({"tag": tag, "status": resp.status, "n": n, "url": u, "keys": keys,
                     "size": len(body), "method": resp.request.method, "post": post})
        fn = os.path.join(OUT, f"manage_{tag}_{len(rows):02d}_{host}_{tag_of(u)}.json")
        open(fn, "w", encoding="utf-8").write(body)

    page.on("response", on_resp)
    log(f"\n### {tag}: {url[:100]}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log(f"goto 异常(继续): {str(e)[:80]}")
    await asyncio.sleep(wait)
    log(f"标题: {await page.title()} | 最终 URL: {page.url[:110]}")
    for r in sorted(rows, key=lambda x: -x["size"]):
        log(f"  {r['method']} n={r['n']:>4} {r['size']:>8}B {r['url'].split('?')[0][-62:]}")
    await page.close()
    return rows


async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=18)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    allrows = []
    for tag, url in PAGES:
        allrows += await run_page(ctx, tag, url, a.wait)
        await asyncio.sleep(3)
    with open(os.path.join(OUT, "manage_index.txt"), "w", encoding="utf-8") as f:
        for r in allrows:
            f.write(json.dumps({k: v for k, v in r.items() if k != "post"}, ensure_ascii=False) + "\n")
            if r.get("post"):
                f.write("   POST " + str(r["post"])[:900] + "\n")
    log(f"\n共 {len(allrows)} 个接口 -> probe_alimama_out/manage_index.txt")
    # 计划清单接口单独打出来: 关心它带不带 campaignId/名称/指标
    for r in allrows:
        if "campaign" in r["url"] and r["n"] > 1:
            log(f"\n候选计划清单接口 [{r['tag']}] n={r['n']} {r['url'].split('?')[0]}")
            log(f"  首行字段: {','.join(r['keys'][:26])}")
    await b.close()


if __name__ == "__main__":
    asyncio.run(main())
