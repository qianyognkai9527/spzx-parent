#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_replay.py — 验证阿里妈妈报表接口能否按日期/维度重放.

思路: 报表页自己会发一次 report/query.json, 从那次请求里借 csrfId + loginPointId
      与请求头, 然后在**同一个页面上下文里**改参数重发 fetch。
      为什么在页面里发而不是 python 直连: cookie 是 httpOnly 拿不全, 且 bx-v 这类
      行为验证头由页面 ajax 层生成, 脱离页面重放大概率被判异常。

全程只读: 只调 report/query.json 这一个查询接口, 不点任何按钮, 不碰出价/预算/计划。

跑法: automation/venv/bin/python probe_alimama_replay.py
产物: probe_alimama_out/replay_<用例>.json
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
PAGE_URL = ("https://one.alimama.com/index.html#!/manage/search-detail?mx_bizCode=onebpSearch"
            "&bizCode=onebpSearch&tab=&startTime=2026-10-01&endTime=2026-10-01&campaignId=83392769388")
CAMPAIGN = "83392769388"
FIELDS = ["adPv", "click", "charge", "ctr", "ecpc", "ecpm", "roi", "cvr",
          "alipayInshopAmt", "alipayInshopNum", "alipayDirAmt", "alipayDirNum",
          "alipayIndirAmt", "alipayIndirNum", "cartInshopNum", "itemColInshopNum",
          "shopColDirNum", "colNum", "colCartNum", "itemColCart"]


def log(m):
    print(m, flush=True)


async def main():
    os.makedirs(OUT, exist_ok=True)
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    page = await ctx.new_page()

    template = {}

    async def on_req(req):
        if template or "report/query.json" not in req.url:
            return
        try:
            body = json.loads(req.post_data or "{}")
        except Exception:
            return
        if "campaignId" not in body:
            return
        template["url"] = req.url
        template["body"] = body
        template["headers"] = {k: v for k, v in (req.headers or {}).items()
                               if k.lower() in ("content-type", "accept", "bx-v")}

    page.on("request", on_req)
    log(f"打开报表页借一次真实请求参数: {PAGE_URL[:80]}")
    try:
        await page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log(f"goto 异常(继续): {str(e)[:80]}")
    for _ in range(20):
        await asyncio.sleep(1.5)
        if template:
            break
    if not template:
        log("!! 没抓到模板请求 —— 登录态掉了或页面结构变了")
        await page.close()
        await b.close()
        return
    log(f"模板到手: csrfId={template['body'].get('csrfId','')[:24]}… "
        f"loginPointId={str(template['body'].get('loginPointId'))[:20]}… "
        f"sourceList={template['body'].get('sourceList')}")

    async def call(name, patch):
        body = dict(template["body"])
        body.update(patch)
        r = await page.evaluate("""async ([url, hdrs, body]) => {
            const res = await fetch(url, {method:'POST', headers: hdrs, body: JSON.stringify(body),
                                          credentials:'include'});
            const t = await res.text();
            return {status: res.status, text: t};
        }""", [template["url"], template["headers"], body])
        txt = r["text"]
        path = os.path.join(OUT, f"replay_{name}.json")
        open(path, "w", encoding="utf-8").write(txt)
        try:
            j = json.loads(txt)
        except Exception:
            log(f"[{name}] HTTP {r['status']} 非 JSON ({len(txt)}B): {txt[:120]}")
            return
        lst = (j.get("data") or {}).get("list")
        info = j.get("info") or {}
        n = len(lst) if isinstance(lst, list) else -1
        log(f"[{name}] HTTP {r['status']} 行数={n} ok={info.get('ok')} "
            f"msg={str(info.get('message'))[:60]} err={info.get('errorCode')}")
        if isinstance(lst, list) and lst:
            keys = sorted(lst[0].keys())
            log(f"    首行字段({len(keys)}): {','.join(keys[:16])}…")
            log(f"    样本: charge={lst[0].get('charge')} adPv={lst[0].get('adPv')} "
                f"click={lst[0].get('click')} ctr={lst[0].get('ctr')} roi={lst[0].get('roi')} "
                f"thedate={lst[0].get('thedate')} hourId={lst[0].get('hourId')}")
        elif n == 0:
            log(f"    空结果. body 关键参数: {json.dumps({k: body.get(k) for k in ('startTime','endTime','tab','sourceList','queryDomains','fromRealTime','splitType')}, ensure_ascii=False)}")

    log("\n=== 用例 ===")
    await call("A_same_as_page", {"startTime": "2026-10-01", "endTime": "2026-10-01",
                                  "fromRealTime": False, "splitType": "sum", "queryDomains": []})
    await call("B_daily_series", {"startTime": "2026-09-20", "endTime": "2026-10-02",
                                  "fromRealTime": False, "splitType": "sum",
                                  "queryDomains": ["date"]})
    await call("C_yesterday", {"startTime": "2026-10-02", "endTime": "2026-10-02",
                               "fromRealTime": False, "allDay": True, "fromHourTable": True,
                               "splitType": "sum", "queryDomains": []})
    await call("D_adgroup", {"tab": "adgroup", "startTime": "2026-10-01", "endTime": "2026-10-01",
                             "sourceList": ["campaign_detail", "adgroup_list"],
                             "byPage": False, "fromRealTime": False, "splitType": "sum",
                             "computeType": "sum", "queryDomains": []})
    await call("E_word", {"tab": "word", "startTime": "2026-10-01", "endTime": "2026-10-01",
                          "sourceList": ["campaign_detail", "word_list"],
                          "byPage": False, "fromRealTime": False, "splitType": "sum",
                          "queryDomains": []})
    await call("F_crowd", {"tab": "crowd", "startTime": "2026-10-01", "endTime": "2026-10-01",
                           "sourceList": ["campaign_detail", "crowd_list"],
                           "byPage": False, "fromRealTime": False, "splitType": "sum",
                           "queryDomains": []})
    await call("G_item", {"tab": "item", "startTime": "2026-10-01", "endTime": "2026-10-01",
                          "sourceList": ["campaign_detail", "item_list"],
                          "byPage": False, "fromRealTime": False, "splitType": "sum",
                          "queryDomains": []})
    await call("H_creative", {"tab": "creative", "startTime": "2026-10-01", "endTime": "2026-10-01",
                              "sourceList": ["campaign_detail", "creative_list"],
                              "byPage": False, "fromRealTime": False, "splitType": "sum",
                              "queryDomains": []})

    await page.close()
    await b.close()
    log("\n完成。用例响应都在 probe_alimama_out/replay_*.json")


if __name__ == "__main__":
    asyncio.run(main())
