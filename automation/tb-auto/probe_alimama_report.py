#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_report.py — 探阿里妈妈(万相台无界版)报表页的数据接口.

只读: 新开 tab → goto 报表页 → 录下所有 JSON 响应 → 落盘. 不点任何按钮、不碰出价/预算/计划.

为什么走接口而不是导出: 后台报表页是 SPA, 表格数据本来就是 XHR 拉的,
导出按钮不可用时, 直接复用它自己的接口是唯一能批量拿的路子。

跑法: automation/venv/bin/python probe_alimama_report.py [--url <报表页地址>]
产物: probe_alimama_out/<序号>_<host>_<路径摘要>.json + index.txt
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_alimama_out")
DEFAULT_URL = ("https://one.alimama.com/index.html?spm=a21dvs.28495141.cc92828ac.dbf3edac0.52d9645eyJUcTi"
               "#!/manage/search-detail?mx_bizCode=onebpSearch&bizCode=onebpSearch&tab=&"
               "startTime=2026-10-02&endTime=2026-10-02&campaignId=83392769388")
# 静态资源与埋点不是目标, 按路径关键词排除
SKIP_HOST = ("g.alicdn.com", "gm.mmstat.com", "log.mmstat.com", "fourier.taobao.com",
             "retcode.alicdn.com", "d.alicdn.com", "img.alicdn.com", "gw.alicdn.com",
             "losvc.alibaba-inc.com", "umdc.alipay.com")
DATA_HINT = ("report", "query", "list", "detail", "data", "campaign", "stat", "summary",
             "get", "search", "record", "chart", "metric")


def log(m):
    print(m, flush=True)


def slug(url):
    path = re.sub(r"[^a-zA-Z0-9_.-]", "_", url.split("?")[0].split("//")[-1])[:90]
    return path + "_" + hashlib.md5(url.encode()).hexdigest()[:8]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--wait", type=int, default=25, help="页面加载后多等几秒等异步接口")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # keep_urls 必须盖住用户当前开着的 tab, 否则 connect_cdp 的启动清理会把它们关掉
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    page = await ctx.new_page()
    captured = []

    async def on_resp(resp):
        u = resp.url
        host = u.split("//")[-1].split("/")[0] if "//" in u else ""
        if any(s in host for s in SKIP_HOST):
            return
        ct = (resp.headers or {}).get("content-type", "")
        if "json" not in ct and "text/plain" not in ct:
            return
        low = u.lower()
        if not any(h in low for h in DATA_HINT):
            return
        try:
            body = await resp.text()
        except Exception:
            return
        if len(body) < 40:
            return
        captured.append((resp.status, len(body), u, body))

    page.on("response", on_resp)

    # 请求侧: 重放需要 method + 请求体 + 关键头(csrfId 在 query 里, 但 cookie/UA 必须一致)
    reqs = []

    async def on_req(req):
        if "report/query.json" not in req.url:
            return
        try:
            post = req.post_data
        except Exception:
            post = None
        hdr = {k: v for k, v in (req.headers or {}).items()
               if k.lower() in ("content-type", "accept", "referer", "user-agent", "bx-v", "x-xsrf-token")}
        reqs.append({"method": req.method, "url": req.url, "headers": hdr, "post_data": post})

    page.on("request", on_req)
    log(f"goto {a.url[:110]}")
    try:
        await page.goto(a.url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log(f"goto 异常(继续观察): {str(e)[:90]}")
    await asyncio.sleep(a.wait)

    title = await page.title()
    log(f"\n标题: {title}\n最终 URL: {page.url}")
    try:
        text = await page.inner_text("body")
    except Exception:
        text = ""
    log(f"正文前 400 字:\n{text[:400]}\n")

    log(f"捕获 JSON 响应 {len(captured)} 条")
    index = []
    for i, (status, size, u, body) in enumerate(sorted(captured, key=lambda x: -x[1]), 1):
        host = u.split("//")[-1].split("/")[0]
        fname = f"{i:02d}_{host}_{slug(u)}.json"
        with open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(body)
        preview = body[:160].replace("\n", " ")
        index.append(f"{i:02d} {status} {size:>8}B {host} {u.split('?')[0][-70:]}\n     {preview}")
        log(f"[{i:02d}] {status} {size:>8}B {u[:120]}")
    with open(os.path.join(OUT, "index.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(index))
    log(f"\nWROTE {OUT}/index.txt")

    with open(os.path.join(OUT, "requests.txt"), "w", encoding="utf-8") as f:
        f.write(json.dumps(reqs, ensure_ascii=False, indent=2))
    log(f"report/query.json 请求 {len(reqs)} 条 -> requests.txt")
    for r in reqs[:6]:
        log(f"  {r['method']} post={str(r['post_data'])[:200]}")

    await page.close()
    await b.close()


if __name__ == "__main__":
    asyncio.run(main())
