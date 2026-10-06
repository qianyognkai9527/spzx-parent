#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回店铺核对: 抓拼多多在售清单, 落 pdd_store_snapshot.json.

跑法: automation/venv/bin/python sync_pdd_store.py [--check]
  前置: 9224 的 Chrome 已起且登录态在 chrome-profile 里(run_chrome_pdd.sh)

为什么要这个脚本: create_pdd_product 判"成功"只看有没有跳到成功页, 而成功页的
wait_audit=false 只代表**提交被受理** —— 拼多多之后仍会驳回(2026-10-05 实测 199 条台账
里 5 条被驳, 全是品牌管控)。所以"铺了多少件"必须以店铺在售清单为准, 不能只信 done。
--check 顺手把台账和在售名单对一遍, 打印差额。
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402
import pdd_compliance as G  # noqa: E402

SNAPSHOT = C.SNAPSHOT
REJECTIONS = C.REJECTIONS
COUNT_API = "vodka/v2/mms/query/display/mall_goods/count"

ROW_JS = """()=>[...document.querySelectorAll('tr')].map(r=>(r.innerText||'').split('\\n')
    .map(s=>s.trim()).filter(Boolean))
  .filter(a=>a.some(s=>/^ID: ?\\d{6,}$/.test(s)))
  .map(a=>{
    const i=a.findIndex(s=>/^ID: ?\\d{6,}$/.test(s));
    const num=(k)=>{const j=a.indexOf(k);return j>0?a[j-1]:''};
    return {goods_id:a[i].replace(/\\D+/g,''), title:a[i-1]||'',
            price:num('修改价格'), stock:num('修改库存'), raw:a.join(' | ')};
  })"""


def click_tab(page, name):
    """按 Tab 文本(形如「已驳回(5)」)点过去。返回是否点到。"""
    return page.evaluate(
        """(w)=>{const els=[...document.querySelectorAll('li,div,span')]
             .filter(e=>(e.textContent||'').trim().startsWith(w)&&e.textContent.length<24);
           if(!els.length) return false; els[els.length-1].click(); return true;}""", name)


def candidate_brand_words(rejections, on_sale):
    """提名逻辑单一来源在 pdd_compliance —— 这里只做转发，避免两份实现各自漂移。"""
    return G.candidate_brand_words(rejections, on_sale)


async def collect_all(page):
    """把当前 Tab 的表格逐页收干净, 返回 {goods_id: row}."""
    out = {}
    for _ in range(60):
        for r in await page.evaluate(ROW_JS):
            out.setdefault(r["goods_id"], r)
        cur = await page.evaluate(
            """()=>{const e=document.querySelector('li[class*=pagerItemActive]');
               return e?(e.textContent||'').trim():'';}""")
        last = await page.evaluate(
            """()=>{const t=[...document.querySelectorAll('li[class*=pagerItem]')]
                 .map(x=>(x.textContent||'').trim()).filter(x=>/^\\d+$/.test(x));
               return t.length?Math.max(...t.map(Number)):0;}""")
        nxt = int(cur or 1) + 1
        if not last or nxt > last:
            break
        moved = await page.evaluate(
            """(n)=>{const e=[...document.querySelectorAll('li[class*=pagerItem]')]
                 .find(x=>(x.textContent||'').trim()===String(n));
                 if(!e)return false;e.click();return true;}""", nxt)
        if not moved:
            break
        await asyncio.sleep(3.2)
    return out


async def scrape():
    b, ctx = await connect_cdp(C.CDP_PORT, keep_urls=["pinduoduo.com"], log=print)
    page = await ctx.new_page()
    counts = {}

    async def on_resp(r):
        if COUNT_API in r.url:
            try:
                counts.update(json.loads(await r.text()).get("result") or {})
            except Exception:
                pass

    page.on("response", on_resp)
    await page.goto(C.MMS_GOODS_LIST, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(8)
    on_sale = await collect_all(page)
    rejected = {}
    if await click_tab(page, "已驳回"):
        await asyncio.sleep(6)
        rejected = await collect_all(page)
    await page.close()
    await b.close()
    return list(on_sale.values()), list(rejected.values()), counts


def check(rows):
    """台账(pdd_products.jsonl) vs 在售清单, 只打印差额, 不写库."""
    live = {r["goods_id"] for r in rows}
    logged = {}
    for l in open(C.PDD_PRODUCTS, encoding="utf-8"):
        r = json.loads(l)
        logged[str(r["pdd_goods_id"])] = r
    gone = [g for g in logged if g not in live]
    print(f"台账 {len(logged)} 条 | 在售 {len(live)} 条")
    print(f"台账里但不在售(被驳回/下架/删除) {len(gone)} 条:")
    for g in gone:
        print(f"  - {g} {logged[g]['item_id']} {logged[g]['title'][:40]}")
    extra = [g for g in live if g not in logged]
    print(f"在售但台账没有(人工建的或落盘失败) {len(extra)} 条")
    for g in extra[:10]:
        print(f"  + {g}")


def reason_of(row):
    """从整行文本里截出驳回/审核原因那一段(表格里紧跟「发布已驳回」之后)."""
    raw = row.get("raw", "")
    m = re.search(r"发布已驳回\s*\|?\s*(.+?)(?:\s*\|\s*(?:主账号|操作|查看|$))", raw)
    return (m.group(1) if m else raw)[:400]


def load_rejections():
    """驳回台账: 按 goods_id 累积。文件不存在返回空 dict。"""
    if not os.path.exists(REJECTIONS):
        return {}
    try:
        doc = json.load(open(REJECTIONS, encoding="utf-8"))
    except Exception:
        return {}
    return {r["goods_id"]: r for r in doc.get("rejected") or []}


def report_rejections(rejected, on_sale):
    """把这次看到的驳回并入台账, 再提名品牌词候选.

    为什么必须落盘而不是每次现抓: 「已驳回」Tab 是**临时的** —— 2026-10-05 上午还是 5 条,
    当天下午同一个 Tab 变成 0 条(也没进"已删除")。只信页面等于把刚学到的品牌词丢掉。
    """
    known = load_rejections()
    for r in rejected:
        known[r["goods_id"]] = {"goods_id": r["goods_id"], "title": r["title"],
                                "reason": reason_of(r),
                                "seen_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    doc = {"updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "rejected": sorted(known.values(), key=lambda x: x.get("seen_at", ""))}
    tmp = REJECTIONS + ".tmp"
    json.dump(doc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, REJECTIONS)
    print(f"\n本次页面看到驳回 {len(rejected)} 条 | 驳回台账累计 {len(known)} 条 -> {REJECTIONS}")
    for r in doc["rejected"]:
        print(f"  - {r['goods_id']} {r['title'][:34]}")
        print(f"    原因: {r['reason'][:110]}")
    words = set(C.BRAND_WORDS)
    cands = [(w, n) for w, n in candidate_brand_words(doc["rejected"], on_sale) if w not in words]
    if cands:
        print("品牌词候选(只出现在驳回标题、在售里查无此词；**要人确认再进 BRAND_WORDS**):")
        for w, n in cands[:15]:
            print(f"  {w}  命中 {n} 条驳回")
    else:
        print("没有新的品牌词候选 —— 驳回里的词都已在 BRAND_WORDS，或在售标题里也出现过")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只对差额, 不覆盖快照")
    args = ap.parse_args()
    rows, rejected, counts = asyncio.run(scrape())
    if not rows:
        # 抓不到行通常不是页面空, 而是登录态掉了或 9224 起了别的 profile —— 别把空清单写成快照
        print("!! 在售清单抓到 0 行, 判定为未登录/选择器失效, 不写快照")
        sys.exit(3)
    print(f"在售 {len(rows)} 行 | count 接口: " +
          " ".join(f"{k}={v}" for k, v in counts.items() if isinstance(v, int)))
    slim = [{k: v for k, v in r.items() if k != "raw"} for r in rows]
    # 页面这一轮没看到驳回也要跑：台账是累积的，品牌词提名要用历史全量而不是今天这一屏
    report_rejections(rejected, rows)
    if args.check:
        check(rows)
        return
    doc = {"scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "counts": counts, "on_sale": slim}
    tmp = SNAPSHOT + ".tmp"
    json.dump(doc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, SNAPSHOT)
    print(f"WROTE {SNAPSHOT} ({len(slim)} 条在售)")


if __name__ == "__main__":
    main()
