#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_alimama_word_tab.py — 抓万相台单元详情页【关键词】tab 的词级报表 XHR.

背景: collect_alimama_promo.py 计划/单元/人群三层已通, 词层接口形态未知。
前两轮探针(report/query.json+tab=word、监听 search-detail 页)只拿到计划汇总行与
component/findList.json —— 这次记录**全部** .json 响应体, 先抓全再人工筛。

用法(先确保 9222 Chrome 已登录万相台、窗口模式、无其他长任务在 9222 上跑):
    automation/venv/bin/python tb-auto/probe_alimama_word_tab.py \
        --campaign-id 84290744044 [--adgroup-id <id>] [--seconds 40]

产物: tb-auto/probe_alimama_out/ 下
  index.json          每个响应一行(file/url/status/长度/命中特征)
  resp_NNN.json       完整响应体
  word_template.json  命中词行特征的候选清单(人工确认后作为采集器词层依据)
只读: 只打开页面与监听, 不点任何写操作按钮。
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import collect_alimama_promo as cap  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_alimama_out")
DETAIL_URL = ("https://one.alimama.com/index.html#!/manage/search-detail"
              "?mx_bizCode=onebpSearch&bizCode=onebpSearch&startTime={d}&endTime={d}"
              "&campaignId={cid}&tab=&adgroupId={aid}")


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


async def main(a):
    os.makedirs(OUT, exist_ok=True)
    day = time.strftime("%F")
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    seen = []
    idx = {"n": 0}

    def on_resp(resp):
        if ".json" not in resp.url:
            return
        n = idx["n"] = idx["n"] + 1
        name = f"resp_{n:03d}.json"

        async def grab():
            try:
                body = await resp.text()
            except Exception:
                body = ""
            hits = [w for w in ("bidword", "reportInfoList", "crowdId", "wordList") if w in body]
            seen.append({"file": name, "url": resp.url[:300], "status": resp.status,
                         "len": len(body), "hits": hits})
            with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
                f.write(body)

        asyncio.ensure_future(grab())

    page = await ctx.new_page()
    page.on("response", on_resp)
    try:
        tpl = await cap.borrow_template(page, "onebpSearch", day)
        if not tpl:
            log("!! 没借到 findPage 参数(登录态掉了?) —— 人工打开万相台后台后再跑")
            return 2
        aid = a.adgroup_id
        if not aid:
            status, text = await cap.fetch_adgroups(page, tpl, "onebpSearch",
                                                    a.campaign_id, day, 0, 200)
            lst = ((json.loads(text).get("data") or {}).get("list")) or []
            if not lst:
                log("!! 该计划拿不到单元, 用 --adgroup-id 手动指定")
                return 2
            aid = lst[0].get("adgroupId")
        log(f"单元详情页 adgroupId={aid}, 监听 {a.seconds}s …")
        await page.goto(DETAIL_URL.format(d=day, cid=a.campaign_id, aid=aid),
                        wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(a.seconds)
        try:
            await page.click('text=人群', timeout=5000)
            await asyncio.sleep(8)
            log("已切【人群】tab(用于核对 crowd 接口形态)")
        except Exception:
            log("未找到人群 tab(该单元可能没配人群), 继续")
    finally:
        with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=1)
        try:
            await page.close()
        except Exception:
            pass
        await b.close()

    cand = [s for s in seen if "bidword" in s["hits"] and "reportInfoList" in s["hits"]]
    crowd = [s for s in seen if "crowdId" in s["hits"]]
    with open(os.path.join(OUT, "word_template.json"), "w", encoding="utf-8") as f:
        json.dump({"candidates": cand, "crowd_seen": crowd,
                   "note": "人工确认 URL/sourceList/词id字段/词文本字段 后回填采集器"},
                  f, ensure_ascii=False, indent=1)
    log(f"共记录 {len(seen)} 个 json 响应 → {OUT}")
    for s in cand:
        log(f"  词级候选: {s['file']} len={s['len']} {s['url'][:120]}")
    if not cand:
        log("!! 没有命中 bidword+reportInfoList 的响应 —— 检查 index.json 里点【关键词】tab 后的新增响应")
        return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", default="84290744044")
    ap.add_argument("--adgroup-id", default=None)
    ap.add_argument("--seconds", type=int, default=40)
    sys.exit(asyncio.run(main(ap.parse_args())))
