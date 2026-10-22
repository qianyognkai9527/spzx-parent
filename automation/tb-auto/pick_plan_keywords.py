#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pick_plan_keywords.py — 给阿里妈妈「关键词推广标准计划」每个单元重新选词 + 按公式算出价写入。

适用场景：标准计划建错要重建。新计划的商品(单元)/分时折扣由用户在页面选好；关键词不用照搬旧计划，
而是**重新选**：平台推荐候选 + 标题派生约束筛词，再对每个词查手淘市场均价、按公式算出基础出价，
以**广泛匹配**写入新计划对应单元。

出价公式（与 KwBidCalculator / adjust_alimama_bid.py 同口径）：
    关键词出价(基础出价) = 手淘市场均价 / ((1 + 人群溢价%) × 分时折扣%)
    默认 溢价 300% / 折扣 35% -> 除以 1.4；全能调价未开不计。
    money_floor2 向下取到分；低于 min-bid(0.05) 抬到 min-bid；查不到「手淘」均价则跳过记录不猜。

选词（完全复用 add_alimama_keywords.py 的规则）：
    候选来源=平台推荐接口 /bidword/suggest/kr/list.json（AI选词 kr_fill_by_item + 趋势机会词 kr_new_mta）；
    过滤：搜索指数>=min-index(1000, 兜底200)、长度>=2、无虚词、须含标题品类家族名词且不落别家族、
    领型/长度冲突剔除(可选材质)；按搜索指数降序取前 top；对单元已有词与两来源去重。

写入：POST /bidword/add.json，payload 每词带各自 bidPrice 与 matchScope(默认 4=广泛)。

跑法（默认 dry-run，只有 --apply 才写）：
  automation/venv/bin/python pick_plan_keywords.py --campaign-id <新id> --limit-units 2 --dry-run
  automation/venv/bin/python pick_plan_keywords.py --campaign-id <新id> --apply --top 30

前置：9222 窗口模式 Chrome 已登录万相台（本脚本只连 9222）。
续跑：报告 json 是唯一状态；重跑时按 (adgroupId, word) 就地更新，已写入的词会因出现在单元页而被去重跳过。
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import quote

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

import add_alimama_keywords as akw  # noqa: E402
import adjust_alimama_bid as akb  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT = os.path.join(BASE, "pick_keywords_report.json")
TRAFFIC = akb.TRAFFIC


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


# ---------------- 纯函数（可单测） ----------------

def bq(word):
    """词在流量解析 URL 里是**双重** URL 编码（实测 女皮草 -> %25E5%25A5...）。"""
    return quote(quote(word or "", safe=""), safe="")


def build_traffic_hash(word, cid="", aid=""):
    return (f"#!/insight/search/traffic-analysis/index?word={bq(word)}"
            f"&campaignId={cid}&adgroupId={aid}&bidwordId=")


# 品牌词黑名单：命中即剔（2026-10-17 用户要求，琳琳皮草/cc皮草/羽绒服鸭鸭 等品牌词混入选词）。
# 已实测混入的 + 本店类目常见品牌；可用 --brand-blocklist 追加，建议后续随平台发现持续补。
BRAND_TOKENS = [
    "琳琳", "cc", "鸭鸭", "波司登", "雪中飞", "雅鹿", "高梵", "鄂尔多斯",
    "恒源祥", "南极人", "优衣库", "太平鸟", "探路者", "骆驼", "啄木鸟",
    # 睡衣/家居服品牌（2026-10-17 睡衣单元 dry-run 实测混入野兽派后补）
    "野兽派", "猫人", "三枪", "秋鹿", "芬腾",
]


def is_brand_word(word, extra_tokens=()):
    """品牌词判定：含黑名单 token，或含 ≥2 连续英文字母（cc皮草/t恤中的 T 保留、cc 剔）。"""
    w = (word or "").lower()
    if not w:
        return False
    if re.search(r"[a-z]{2,}", w):
        return True
    for t in list(BRAND_TOKENS) + list(extra_tokens):
        if t and t.lower() in w:
            return True
    return False


def filter_brand_words(picked, extra_tokens=()):
    """从候选里剔品牌词。返回 (保留, 剔除词列表)。"""
    keep, dropped = [], []
    for p in picked:
        (dropped if is_brand_word(p.get("word"), extra_tokens) else keep).append(p)
    return keep, dropped


def upsert(rep, aid, word, item):
    """按 (adgroupId, word) 就地更新，避免复跑堆重复行。"""
    for i, old in enumerate(rep["items"]):
        if old.get("adgroupId") == aid and old.get("word") == word:
            rep["items"][i] = item
            return
    rep["items"].append(item)


# ---------------- 报告 IO ----------------

def load_report(path):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}


def save_report(path, rep):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------------- 写入 ----------------

async def add_words_with_bid(page, cid, aid, items, tok, logf):
    """items: [{"word","bid","matchScope"}]。返回 (ok, msg)。"""
    payload = {"bizCode": "onebpSearch", "csrfId": tok.get("csrfId"),
               "loginPointId": tok.get("loginPointId"), "bidwordList": []}
    for it in items:
        payload["bidwordList"].append({"campaignId": cid, "adgroupId": aid,
                                       "word": it["word"], "bidPrice": it["bid"],
                                       "matchScope": it["matchScope"], "recReason": None})
    res = await page.evaluate(r"""(p) => fetch('/bidword/add.json',
        {method:'POST', headers:{'content-type':'application/json'}, credentials:'include',
         body: JSON.stringify(p)}).then(r=>r.json()).then(j=>{
           const info=j.info||{};
           return {ok: info.ok!==false, err: info.message||info.errorMsg||null};
         }).catch(e=>({ok:false, err:String(e)}))""", payload)
    if not res.get("ok"):
        return False, str(res.get("err"))
    return True, "ok"


# ---------------- 主流程 ----------------

async def collect_candidates(page, args, title, accepted, fam, t_collar, t_length, t_mats,
                             exclude, store, stamp, logf):
    """开抽屉→切 tab 捕两来源候选→选词。返回 picked_all(去重后的 dict 列表)。"""
    if not await akw.open_drawer(page):
        return None, "no_drawer"
    await asyncio.sleep(6)
    picked_all = []
    seen = set(exclude)

    for method, typ in (("ai", "kr_fill_by_item"), ("mta", "kr_new_mta")):
        t0 = time.time()
        if method == "ai":
            await akw.click_tab(page, "关键词推荐")   # 先切走
            await asyncio.sleep(2)
            await akw.click_tab(page, "AI选词")        # 再切回（防缓存）
        else:
            await akw.click_tab(page, "关键词推荐")
            await asyncio.sleep(2)
            await akw.click_sub(page, "趋势机会词")
        cands = await akw._wait_type(store, stamp, typ, t0, timeout=14) or []
        picked, dropped = akw._pick_with_fallback(cands, args, title, accepted, fam,
                                                  t_collar, t_length, t_mats, seen)
        logf(f"   {method}: 候选 {len(cands)} → 入选 {len(picked)} / 剔除 {len(dropped)}")
        for p in picked:
            logf(f"      + {p['word']} (idx={p['searchIndex']})")
            picked_all.append(p)
            seen.add(akw.norm(p["word"]))
    return picked_all, None


async def run(args):
    day = date.today().isoformat()
    rep = load_report(args.report)
    log(f"计划 {args.campaign_id} | 溢价{args.premium}% 折扣{args.discount}% 来源={args.source} "
        f"| top={args.top} matchScope={args.match_scope} | {'DRY-RUN' if args.dry_run else 'APPLY'}")

    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    market_cache = {}
    no_market_streak = 0
    tok = {"csrfId": None, "loginPointId": None}
    store, stamp = {}, {}

    def on_req(r):
        u = r.url
        if "csrfId=" in u and not tok["csrfId"]:
            import re
            m = re.search(r"csrfId=([^&]+)", u)
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

    async def on_resp(r):
        if "kr/list.json" not in r.url:
            return
        try:
            d = json.loads(await r.text(), strict=False)
        except Exception:
            return
        lst = (d.get("data") or {}).get("list")
        if not isinstance(lst, list):
            return
        tp = ((d.get("data") or {}).get("type"))
        try:
            pd = json.loads(r.request.post_data or "{}")
            tp = pd.get("type") or pd.get("selectedKeywordType") or tp
        except Exception:
            pass
        if tp:
            store[tp] = lst
            stamp[tp] = time.time()

    try:
        page = next((p for p in ctx.pages if "alimama.com" in p.url), None)
        if page is None:
            page = await ctx.new_page()
        for p in list(ctx.pages):
            if p is not page:
                try:
                    await p.close()
                except Exception:
                    pass
        page.on("request", on_req)
        page.on("response", lambda r: asyncio.create_task(on_resp(r)))

        units = await akw.get_units(page, args.campaign_id, day, log)
        if not units:
            log("!! 没读到单元列表（登录态掉了 / 计划 id 不对？）")
            return 2
        if args.adgroup_id:
            want = set(args.adgroup_id.split(","))
            units = [u for u in units if u["adgroupId"] in want]

        mkt_page = await ctx.new_page()
        done = 0
        for ui, u in enumerate(units, 1):
            if args.limit_units and done >= args.limit_units:
                log(f"已达 --limit-units {args.limit_units}，停止")
                break
            aid, title = u["adgroupId"], u["title"]
            log(f"[{ui}/{len(units)}] 单元 {aid} | {title[:30]}")

            if not await akw.goto_unit(page, args.campaign_id, aid, day, log):
                log("   !! 单元页未就绪，跳过")
                upsert(rep, aid, "", {"adgroupId": aid, "title": title,
                                      "status": "skip_unit", "note": "no_unit_page"})
                save_report(args.report, rep)
                continue
            await asyncio.sleep(1)
            exist = await akw.existing_words(page)
            accepted, fam = akw.accepted_terms(title)
            t_collar = akw.pick_dim(title, akw.COLLARS)
            t_length = akw.pick_dim(title, akw.LENGTHS)
            t_mats = akw.dims_in(title, akw.MATERIALS)
            log(f"   属性 family={fam} collar={t_collar} length={t_length} | 已有词 {len(exist)}")

            picked_all, err = await collect_candidates(
                page, args, title, accepted, fam, t_collar, t_length, t_mats,
                {akw.norm(w) for w in exist}, store, stamp, log)
            if err:
                log(f"   !! 选词失败: {err}")
                upsert(rep, aid, "", {"adgroupId": aid, "title": title,
                                      "status": "skip_unit", "note": err})
                save_report(args.report, rep)
                continue

            picked_all, brand_dropped = filter_brand_words(picked_all, args.brand_blocklist.split(","))
            if brand_dropped:
                log(f"   剔品牌词 {len(brand_dropped)}: "
                    f"{', '.join(p['word'] for p in brand_dropped[:8])}{'…' if len(brand_dropped) > 8 else ''}")

            # 逐词查均价 + 算价
            priced, n_skip = [], 0
            for p in picked_all:
                w = p["word"]
                if w not in market_cache:
                    m = await akb.market_avg(
                        mkt_page, TRAFFIC.format(hash=build_traffic_hash(w)), args.source, log)
                    market_cache[w] = m
                    await asyncio.sleep(args.gap)
                m = market_cache[w]
                if not m or not m.get("price"):
                    no_market_streak += 1
                    n_skip += 1
                    log(f"      · {w} 无「{args.source}」均价，跳过")
                    upsert(rep, aid, w, {"adgroupId": aid, "title": title, "word": w,
                                         "status": "skip_no_market", "ts": time.strftime("%F %T")})
                    save_report(args.report, rep)
                    if no_market_streak >= 8:
                        log("!! 连续 8 次取不到均价，疑似登录态/风控，停止本轮")
                        return 4
                    continue
                no_market_streak = 0
                bid = akb.calc_bid(m["price"], args.premium, args.discount, args.min_bid)
                priced.append({"word": w, "market": m["price"], "bid": bid,
                               "matchScope": args.match_scope, "searchIndex": p.get("searchIndex")})

            if priced:
                bmin = min(x["bid"] for x in priced)
                bmax = max(x["bid"] for x in priced)
                log(f"   → 有价 {len(priced)} 词 (出价 {bmin}~{bmax}) / 无价 {n_skip}")
            else:
                log(f"   → 无可写入词（无价 {n_skip}）")

            if args.dry_run:
                for it in priced:
                    upsert(rep, aid, it["word"], {"adgroupId": aid, "title": title,
                           "word": it["word"], "market": it["market"], "bid": it["bid"],
                           "matchScope": it["matchScope"], "status": "dry",
                           "ts": time.strftime("%F %T")})
                    log(f"      = {it['word']} 均价={it['market']} → 出价={it['bid']} (dry)")
                save_report(args.report, rep)
                done += 1
                continue

            if not priced:
                done += 1
                continue

            ok, msg = await add_words_with_bid(page, args.campaign_id, aid, priced, tok, log)
            for it in priced:
                upsert(rep, aid, it["word"], {"adgroupId": aid, "title": title,
                       "word": it["word"], "market": it["market"], "bid": it["bid"],
                       "matchScope": it["matchScope"], "status": "ok" if ok else "fail",
                       "note": msg, "ts": time.strftime("%F %T")})
            save_report(args.report, rep)
            log(f"   写入 {'OK' if ok else 'FAIL: ' + msg} ({len(priced)} 词)")
            if not ok:
                log("!! 写入异常，停止本轮（先查现场：csrf/风控）")
                return 3
            done += 1
            await asyncio.sleep(args.gap)

        log(f"完成：处理 {done} 个单元，报告 {args.report}")
        return 0
    finally:
        try:
            await b.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", required=True, help="新标准计划的 campaignId")
    ap.add_argument("--adgroup-id", default=None, help="逗号分隔；不给=该计划所有单元")
    ap.add_argument("--premium", type=float, default=300, help="人群溢价%%（默认300）")
    ap.add_argument("--discount", type=float, default=35, help="分时折扣%%（默认35）")
    ap.add_argument("--source", default="手淘", help="市场均价来源行（默认手淘）")
    ap.add_argument("--min-bid", type=float, default=0.05)
    ap.add_argument("--min-index", type=int, default=1000, help="搜索指数下限")
    ap.add_argument("--min-index-fallback", type=int, default=200,
                    help="某来源一个都选不出时放宽到该指数下限再选一次")
    ap.add_argument("--top", type=int, default=30, help="每个来源最多取多少词（默认30）")
    ap.add_argument("--match-scope", type=int, default=4, help="匹配方式（默认4=广泛）")
    ap.add_argument("--gap", type=float, default=2.0, help="查价/单元之间间隔秒数")
    ap.add_argument("--limit-units", type=int, default=0, help="本轮最多处理多少单元")
    ap.add_argument("--material-filter", action="store_true", help="同时按材质维度剔冲突")
    ap.add_argument("--brand-blocklist", default="",
                    help="逗号分隔的追加品牌词黑名单（内置 BRAND_TOKENS 之外）")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="只读+打印，不写入")
    g.add_argument("--apply", action="store_true", help="真正写入")
    a = ap.parse_args()
    if not a.apply:
        a.dry_run = True
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
