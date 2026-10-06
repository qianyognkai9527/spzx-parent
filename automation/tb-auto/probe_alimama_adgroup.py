#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_adgroup.py — 验证「计划×日×宝贝」粒度能否拿到完整指标.

已确认的契约(从详情页 tab=item 真实请求里录下来的, 不是猜的):
  POST adgroup/horizontal/findPage.json
  body.rptQuery.conditionList[].sourceList = ["campaign_detail","adgroup_list"]   ← 关键
  body.campaignIdList = ["<计划id>"]      body.requestSource = "campaignAdgroupHorizontal"
  宝贝ID 在 material.materialId（13 位，与 platform_product.code 同形）

上一轮为什么全失败: 我把 sourceList 放在了请求体顶层。它必须在 rptQuery.conditionList 里面。

只读。跑法: automation/venv/bin/python probe_alimama_adgroup.py [--date 2026-10-01]
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
from collect_alimama_promo import FIELDS_STR  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_alimama_out")
DETAIL = ("https://one.alimama.com/index.html#!/manage/search-detail?mx_bizCode=onebpSearch"
          "&bizCode=onebpSearch&tab=item&startTime={d}&endTime={d}&campaignId={cid}")
ADGROUP_URL = "https://one.alimama.com/adgroup/horizontal/findPage.json"


def log(m):
    print(m, flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-10-01")
    ap.add_argument("--campaign", default="83392769388")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    page = await ctx.new_page()
    try:
        # 借参数：详情页会自己发一次 adgroup findPage，直接复用它那份 body 形状
        tpl = {}

        async def on_req(req):
            if tpl or "adgroup/horizontal/findPage.json" not in req.url:
                return
            try:
                body = json.loads(req.post_data or "{}")
            except Exception:
                return
            if "csrfId" not in body:
                return
            tpl["body"] = body
            tpl["headers"] = {k: v for k, v in (req.headers or {}).items()
                              if k.lower() in ("content-type", "accept", "bx-v")}

        page.on("request", on_req)
        await page.goto(DETAIL.format(d=a.date, cid=a.campaign),
                        wait_until="domcontentloaded", timeout=60000)
        for _ in range(26):
            await asyncio.sleep(1.5)
            if tpl:
                break
        if not tpl:
            log("!! 没借到 adgroup findPage 请求(登录态掉了/页面结构变了)")
            return

        body = dict(tpl["body"])
        body["offset"] = 0
        body["pageSize"] = 200
        body["campaignIdList"] = [a.campaign]
        body["requestSource"] = "campaignAdgroupHorizontal"
        cond = dict((body.get("rptQuery") or {}).get("conditionList", [{}])[0])
        cond.update({"sourceList": ["campaign_detail", "adgroup_list"],
                     "startTime": a.date, "endTime": a.date, "isRt": False})
        body["rptQuery"] = {"fields": FIELDS_STR, "conditionList": [cond]}
        url = ADGROUP_URL + "?csrfId=" + str(tpl["body"].get("csrfId")) + "&bizCode=onebpSearch"
        r = await page.evaluate("""async ([u,h,b]) => {
            const res = await fetch(u,{method:'POST',headers:h,body:JSON.stringify(b),credentials:'include'});
            return {status:res.status, text: await res.text()};
        }""", [url, tpl["headers"], body])

        log(f"HTTP {r['status']} 响应 {len(r['text'])}B")
        open(os.path.join(OUT, f"adgroup_{a.date}.json"), "w", encoding="utf-8").write(r["text"])
        j = json.loads(r["text"])
        rows = ((j.get("data") or {}).get("list")) or []
        log(f"单元(=宝贝) {len(rows)} 个, data.count={(j.get('data') or {}).get('count')}")
        withm = 0
        for x in rows:
            info = (x.get("reportInfoList") or [{}])[0]
            if info.get("charge") is None:
                continue
            withm += 1
            mat = x.get("material") or {}
            log("  宝贝 %s 花费%-7s 展现%-6s 点击%-5s ctr%%%-8s 总成交%-6s 直接%-6s 加购%-3s 名=%s" % (
                mat.get("materialId"), info.get("charge"), info.get("adPv"), info.get("click"),
                info.get("ctr"), info.get("alipayInshopAmt"), info.get("alipayDirAmt"),
                info.get("cartInshopNum"), (x.get("adgroupName") or "")[:26]))
        log(f"\n带 charge 字段的单元 {withm}/{len(rows)}；"
            f"其余只回 roi7d（=当天该宝贝没有任何投放数据）")
        # 宝贝ID 与本地 platform_product.code 能否对上
        ids = [str((x.get("material") or {}).get("materialId")) for x in rows
               if (x.get("material") or {}).get("materialId")]
        log(f"materialId 样本: {ids[:5]}  共 {len(ids)} 个")
    finally:
        await page.close()
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
