#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reprice_plan.py — 用修正后的均价读取，整计划重算关键词出价（update.json 直连）+ 剔品牌词存量。

背景（2026-10-17，计划 84290744044）：
  1. pick_plan_keywords 页内换词路曾有读表竞态：表格渲染慢于接口，部分词的均价
     读到了上一个词的，出价算错。market_avg 已改为从 1468 响应体解析 avgPrice
     （响应与请求一一对应，竞态根除）。本脚本对**已写入**的词全量重算出价。
  2. add.json 只新增不更新（实测 0.66 写入回读仍 0.18）；改价走
     POST /bidword/update.json（直连重放已实测可用；平台传播有数秒延迟，校验须重载页面）。
  3. 品牌词（琳琳皮草/cc皮草等，is_brand_word）存量走 akw.delete_ids 精准删
     （按 bidwordId，不碰其他词），删除后回读单元页核对。

跑法（默认 dry-run，只有 --apply 才写）：
  automation/venv/bin/python tb-auto/reprice_plan.py --campaign-id 84290744044 --premium 500 --dry-run
  automation/venv/bin/python tb-auto/reprice_plan.py --campaign-id 84290744044 --premium 500 --apply
参数：--campaign-id(必填)/--adgroup-id/--premium(300)/--discount(35)/--source(手淘)/--min-bid(0.05)
      /--gap(2)/--limit-units/--brand-blocklist/--report/--no-verify/--dry-run|--apply
报告（reprice_report.json，gitignore）：meta.market 按词缓存均价（断点续跑不重查）；
  items[] 按 bidwordId 就地更新：{bidwordId,word,adgroupId,oldBid,market,newBid,status,ts}
  status ∈ same/ok/skip_no_market/fail/dry；meta.empty_units=词数为 0 的单元（用
  pick_plan_keywords --adgroup-id 补词）；meta.brand_deleted=已删品牌词。
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

import add_alimama_keywords as akw  # noqa: E402
import adjust_alimama_bid as akb  # noqa: E402
import pick_plan_keywords as pk  # noqa: E402  (is_brand_word / build_traffic_hash)

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT = os.path.join(BASE, "reprice_report.json")

READ_BIDS_JS = r"""() => {
  const out = {};
  document.querySelectorAll('tr.keyword-item[data-keyword-id]').forEach(tr => {
    const id = tr.getAttribute('data-keyword-id');
    const cell = document.querySelector('#bidword_' + id + '_price');
    if (cell) out[id] = (cell.innerText || '').trim();
  });
  return out;
}"""


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


def parse_bid(text):
    m = re.search(r"([\d.]+)", text or "")
    return float(m.group(1)) if m else None


def load_report(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return {"meta": {}, "items": []}


def save_report(path, rep):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def upsert_bidword(rep, bwid, item):
    for i, old in enumerate(rep["items"]):
        if str(old.get("bidwordId")) == str(bwid):
            rep["items"][i] = item
            return
    rep["items"].append(item)


async def update_bids(page, cid, aid, batch, tok, logf):
    """直连 /bidword/update.json。batch=[{bidwordId,bidPrice(str)}]。返回 (ok, count, err)。"""
    payload = {"bizCode": "onebpSearch",
               "bidwordList": [{"campaignId": int(cid), "adgroupId": int(aid),
                                "bidwordId": int(b["bidwordId"]),
                                "bidPrice": str(b["bidPrice"]),
                                "bidStrategyInfo": {"status": 0}} for b in batch],
               "csrfId": tok["csrfId"], "loginPointId": tok["loginPointId"]}
    res = await page.evaluate(r"""(p) => fetch('/bidword/update.json',
        {method:'POST', headers:{'content-type':'application/json'}, credentials:'include',
         body: JSON.stringify(p)}).then(r=>r.json()).then(j=>{
           const info=j.info||{};
           return {ok: info.ok!==false, err: info.message||info.errorMsg||null,
                   count:(j.data&&j.data.count)||0};
         }).catch(e=>({ok:false, err:String(e), count:0}))""", payload)
    return bool(res.get("ok")), int(res.get("count") or 0), res.get("err")


async def run(args):
    extra_tokens = [t for t in (args.brand_blocklist or "").split(",") if t]
    mode = "APPLY" if args.apply else "DRY-RUN"
    log(f"计划 {args.campaign_id} | 溢价{args.premium}% 折扣{args.discount}% 来源={args.source} | {mode}")

    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    page = await ctx.new_page()
    mkt_page = await ctx.new_page()
    day = date.today().strftime("%Y-%m-%d")
    tok = {"csrfId": None, "loginPointId": None}

    def on_req(r):
        if "csrfId=" in r.url and not tok["csrfId"]:
            m = re.search(r"csrfId=([^&]+)", r.url)
            if m:
                tok["csrfId"] = m.group(1)
        if r.post_data and '"csrfId"' in r.post_data:
            try:
                d = json.loads(r.post_data)
                if d.get("csrfId"):
                    tok["csrfId"] = d["csrfId"]
                if d.get("loginPointId"):
                    tok["loginPointId"] = d["loginPointId"]
            except Exception:
                pass

    page.on("request", on_req)

    rep = load_report(args.report)
    market_cache = dict(rep.get("meta", {}).get("market", {}))
    rep.setdefault("meta", {})

    # ---- 1. 枚举单元 + 逐单元收词（含现价）+ 标品牌词 ----
    units = await akb.open_units_page(ctx, args.campaign_id, day, log, page)
    if args.adgroup_id:
        want = {x.strip() for x in args.adgroup_id.split(",") if x.strip()}
        units = [u for u in units if str(u["adgroupId"]) in want]
    if args.limit_units:
        units = units[:args.limit_units]
    log(f"单元数 {len(units)}")

    unit_words = {}     # aid -> [(bidwordId, word, oldBid)]
    brand_del = {}      # aid -> [(bidwordId, word)]
    empty_units = []
    for ui, u in enumerate(units, 1):
        aid = str(u["adgroupId"])
        title = (u.get("adgroupName") or u.get("title") or "")[:24]
        if not await akw.goto_unit(page, args.campaign_id, aid, day, log):
            log(f"[{ui}/{len(units)}] 单元 {aid} 页面未就绪，跳过")
            continue
        await asyncio.sleep(1)
        kws = await page.evaluate(akb.READ_KEYWORDS_JS)
        bids = await page.evaluate(READ_BIDS_JS)
        rows, brands = [], []
        for k in kws:
            row = (k["bidwordId"], k["word"], parse_bid(bids.get(k["bidwordId"], "")))
            (brands if pk.is_brand_word(k["word"], extra_tokens) else rows).append(row)
        unit_words[aid] = rows
        if brands:
            brand_del[aid] = brands
        if not kws:
            empty_units.append(aid)
        log(f"[{ui}/{len(units)}] 单元 {aid} | {title} 词数={len(kws)} 品牌={len(brands)}")

    rep["meta"]["empty_units"] = empty_units
    save_report(args.report, rep)

    # ---- 2. 删品牌词（apply）----
    if brand_del:
        log(f"品牌词存量 {sum(len(v) for v in brand_del.values())} 个，分布在 {len(brand_del)} 个单元")
        if args.apply:
            for aid, rows in brand_del.items():
                names = [w for _, w, _ in rows]
                ok, n, note = await akw.delete_ids(page, args.campaign_id, aid,
                                                   [bw for bw, _, _ in rows], tok, log)
                log(f"   删 {aid}: {names} → ok={ok} 响应count={n} ({note})")
                await asyncio.sleep(6)          # 平台传播延迟
                if not await akw.goto_unit(page, args.campaign_id, aid, day, log):
                    continue
                await asyncio.sleep(1)
                kws2 = await page.evaluate(akb.READ_KEYWORDS_JS)
                left = [k["word"] for k in kws2 if pk.is_brand_word(k["word"], extra_tokens)]
                log(f"   复核 {aid}: 剩余品牌词 {len(left)}{(' → ' + ', '.join(left)) if left else ''}")
                rep.setdefault("meta", {}).setdefault("brand_deleted", []).append(
                    {"adgroupId": aid, "words": names, "left": left})
                save_report(args.report, rep)
        else:
            for aid, rows in brand_del.items():
                log(f"   (dry) 将删 {aid}: {[w for _, w, _ in rows]}")

    # ---- 3. 唯一词查价（修正后的 market_avg：1468 响应体解析）----
    uniq = sorted({w for rows in unit_words.values() for _, w, _ in rows})
    log(f"独立词数 {len(uniq)}（缓存命中 {sum(1 for w in uniq if w in market_cache)}）")
    no_market_streak = 0
    for i, w in enumerate(uniq, 1):
        if w in market_cache:
            continue
        m = await akb.market_avg(mkt_page, akb.TRAFFIC.format(hash=pk.build_traffic_hash(w)),
                                 args.source, log)
        market_cache[w] = m.get("price") if m else None
        await asyncio.sleep(args.gap)
        if market_cache[w] is None:
            no_market_streak += 1
            if no_market_streak >= 8:
                log("!! 连续 8 词取不到均价，疑似登录态/风控，停止本轮")
                rep["meta"]["market"] = market_cache
                save_report(args.report, rep)
                return 4
        else:
            no_market_streak = 0
        if i % 20 == 0 or i == len(uniq):
            log(f"   查价 {i}/{len(uniq)}")
            rep["meta"]["market"] = market_cache
            save_report(args.report, rep)
    rep["meta"]["market"] = market_cache
    save_report(args.report, rep)

    # ---- 4. 算价 + 写（跳过现价已正确的）----
    n_same = n_ok = n_skip = n_fail = 0
    for aid, rows in unit_words.items():
        batch, items = [], []
        for bw, w, old in rows:
            price = market_cache.get(w)
            item = {"bidwordId": bw, "word": w, "adgroupId": aid, "oldBid": old,
                    "market": price, "ts": time.strftime("%F %T")}
            if price is None:
                item["status"], item["newBid"] = "skip_no_market", None
                upsert_bidword(rep, bw, item)
                n_skip += 1
                continue
            newbid = akb.calc_bid(price, args.premium, args.discount, args.min_bid)
            item["newBid"] = newbid
            if old is not None and abs(old - newbid) < 0.005:
                item["status"] = "same"
                upsert_bidword(rep, bw, item)
                n_same += 1
                continue
            batch.append({"bidwordId": bw, "bidPrice": f"{newbid:.2f}", "_item": item})
            items.append(item)
        if not batch:
            continue
        if not args.apply:
            for it in items:
                it["status"] = "dry"
                upsert_bidword(rep, it["bidwordId"], it)
            n_ok += len(items)
            continue
        ok, count, err = await update_bids(page, args.campaign_id, aid,
                                           [{k: v for k, v in b.items() if k != "_item"} for b in batch], tok, log)
        if ok and count >= len(batch):
            for b_ in batch:
                b_["_item"]["status"] = "ok"
                upsert_bidword(rep, b_["bidwordId"], b_["_item"])
            n_ok += len(batch)
        else:
            log(f"   !! 批量写 {aid} 回落逐词 (ok={ok} count={count} err={err})")
            for b_ in batch:
                ok1, c1, e1 = await update_bids(page, args.campaign_id, aid,
                                                [{k: v for k, v in b_.items() if k != "_item"}], tok, log)
                b_["_item"]["status"] = "ok" if (ok1 and c1 >= 1) else "fail"
                if not ok1:
                    b_["_item"]["note"] = str(e1)[:80]
                    n_fail += 1
                else:
                    n_ok += 1
                upsert_bidword(rep, b_["bidwordId"], b_["_item"])
                await asyncio.sleep(0.4)
        save_report(args.report, rep)
    save_report(args.report, rep)
    log(f"算价完成: same={n_same} ok={n_ok} skip_no_market={n_skip} fail={n_fail}")

    # ---- 5. 校验（apply 时重载单元页比对）----
    if args.apply and not args.no_verify and n_ok:
        await asyncio.sleep(8)          # 平台传播延迟
        mism = []
        for aid, rows in unit_words.items():
            intend = {str(bw): (market_cache.get(w), akb.calc_bid(market_cache[w], args.premium,
                      args.discount, args.min_bid) if market_cache.get(w) else None)
                      for bw, w, _ in rows}
            if not await akw.goto_unit(page, args.campaign_id, aid, day, log):
                continue
            await asyncio.sleep(1)
            bids = await page.evaluate(READ_BIDS_JS)
            for bw, (_, want) in intend.items():
                got = parse_bid(bids.get(bw, ""))
                if want is not None and got is not None and abs(got - want) >= 0.005:
                    mism.append((aid, bw, got, want))
        log(f"校验: 不一致 {len(mism)}")
        for aid, bw, got, want in mism[:10]:
            log(f"   {aid} {bw} 现价={got} 应为={want}")
        if mism:
            log("   逐词重发不一致项…")
            for aid, bw, got, want in mism:
                ok1, c1, e1 = await update_bids(page, args.campaign_id, aid,
                                                [{"bidwordId": bw, "bidPrice": f"{want:.2f}"}], tok, log)
                log(f"   重发 {bw} → ok={ok1} count={c1} {e1 or ''}")
                await asyncio.sleep(1)
        rep["meta"]["verify_mismatch"] = len(mism)
        save_report(args.report, rep)

    log(f"空单元（无词，可用 pick_plan_keywords --adgroup-id 补）: {empty_units or '无'}")
    await page.close()
    await mkt_page.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", required=True)
    ap.add_argument("--adgroup-id", default=None)
    ap.add_argument("--premium", type=float, default=300)
    ap.add_argument("--discount", type=float, default=35)
    ap.add_argument("--source", default="手淘")
    ap.add_argument("--min-bid", type=float, default=0.05)
    ap.add_argument("--gap", type=float, default=2.0)
    ap.add_argument("--limit-units", type=int, default=0)
    ap.add_argument("--brand-blocklist", default="")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--no-verify", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not a.apply:
        a.dry_run = True
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
