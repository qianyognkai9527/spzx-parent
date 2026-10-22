#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adjust_alimama_bid.py — 按「流量解析→竞争流量透视→手淘市场均价」修正阿里妈妈关键词出价。

规则（与 KwBidCalculator 同口径）：
    关键词出价(基础出价) = 手淘市场均价 / ((1 + 人群溢价%) × 分时折扣%)
    默认 人群溢价 300% / 分时折扣 35% -> 除以 1.4；全能调价未开不计。
    向下取到分；低于 min-bid 时抬到 min-bid；查不到「手淘」行/市场均价则跳过并记录。

只读采集：搜索详情页 bidword 表、流量解析页竞争流量透视表。
写入：点该词「出价」列的 editPrice 图标 -> 弹框选「手动出价」-> 填值 -> 确定 -> 回读校验。

跑法：
  automation/venv/bin/python adjust_alimama_bid.py --campaign-id 83392643008 --dry-run --limit 5
  automation/venv/bin/python adjust_alimama_bid.py --campaign-id 83392643008 --apply
续跑：默认读 --report，已 ok 的词跳过。--adgroup-id 可只跑指定单元。
复跑（行情/季节变了，或改了人群溢价要按新参数重算）：加 --force 忽略历史 ok 整轮重算，
  例如溢价改成 250%：... --apply --force --premium 250。
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from urllib.parse import unquote

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT = os.path.join(BASE, "adjust_bid_report.json")
SEARCH_DETAIL = ("https://one.alimama.com/index.html#!/manage/search-detail"
                 "?mx_bizCode=onebpSearch&bizCode=onebpSearch&campaignId={cid}"
                 "&tab=bidword&startTime={d}&endTime={d}")
TRAFFIC = "https://one.alimama.com/index.html{hash}"  # hash 形如 #!/insight/...


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


def money_floor2(v):
    """向下取到分（与 KwBidCalculator.money 一致）：先修浮点毛刺再 FLOOR。"""
    d = Decimal(str(v)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_FLOOR))


def calc_bid(market, premium_pct, discount_pct, min_bid):
    factor = (1 + premium_pct / 100.0) * (discount_pct / 100.0)
    if factor <= 0:
        return None
    v = money_floor2(market / factor)
    return max(v, money_floor2(min_bid))


# ---------------- 页面读取 ----------------

READ_KEYWORDS_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="traffic-analysis"]').forEach(a => {
    const href = a.getAttribute('href') || '';
    const m = href.match(/bidwordId=(\d+)/);
    if (!m) return;
    const id = m[1];
    if (seen.has(id)) return;
    seen.add(id);
    out.push({ bidwordId: id, word: (a.innerText || '').trim(), href });
  });
  return out;
}
"""

READ_MARKET_JS = r"""
() => {
  const t = e => (e.innerText || '').replace(/\s+/g, ' ').trim();
  // 找含“核心流量来源”的容器，再取其中“手淘”那一行里的 ￥ 数字
  let scope = null;
  const all = [...document.querySelectorAll('div,table,section')];
  for (const e of all) {
    const s = t(e);
    if (s.includes('核心流量来源') && s.includes('市场均价')) { scope = e; break; }
  }
  const root = scope || document.body;
  const rows = [...root.querySelectorAll('tr')];
  for (const tr of rows) {
    const rt = t(tr);
    if (/^手淘/.test(rt) || rt.includes('手淘')) {
      const m = rt.match(/[￥¥]\s*([\d.]+)/);
      if (m) return { source: '手淘', price: parseFloat(m[1]), row: rt.slice(0, 80) };
    }
  }
  // 退化：整块文本里找“手淘 ... ￥x”
  const s = t(root);
  const m = s.match(/手淘[\s\S]{0,60}?[￥¥]\s*([\d.]+)/);
  if (m) return { source: '手淘', price: parseFloat(m[1]), row: m[0].slice(0, 80) };
  return null;
}
"""


async def open_units_page(ctx, campaign_id, day, logf, page):
    """复用给定 page 打开计划搜索详情页(不带 adgroupId)，捕获页面自己的 findPage 拿全部单元。"""
    caps = []
    tpl = {}

    async def on_resp(r):
        if "adgroup/horizontal/findPage.json" not in r.url:
            return
        try:
            post = json.loads(r.request.post_data or "{}")
        except Exception:
            post = {}
        if not tpl and post.get("pageSize", 0) >= 40:
            tpl["url"] = r.url
            tpl["body"] = post
        try:
            j = await r.json()
        except Exception:
            return
        lst = ((j.get("data") or {}).get("list")) or []
        if isinstance(lst, list) and lst and any(x.get("adgroupId") for x in lst):
            caps.append(lst)

    page.on("response", on_resp)
    url = SEARCH_DETAIL.format(cid=campaign_id, d=day)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        logf(f"详情页 goto 异常: {str(e)[:70]}")
    for _ in range(20):
        await asyncio.sleep(1.5)
        if caps and tpl:
            break

    # 用捕获到的 findPage 请求重放 pageSize=200，一次拿全部单元（含暂停）
    rows = max(caps, key=len) if caps else []
    if tpl:
        body = dict(tpl["body"])
        body["pageSize"] = 200
        body["offset"] = 0
        try:
            res = await page.evaluate("""async ([u, b]) => {
                const r = await fetch(u, {method:'POST',
                    headers:{'content-type':'application/json'},
                    body: JSON.stringify(b), credentials:'include'});
                return await r.text();
            }""", [tpl["url"], body])
            j = json.loads(res)
            lst = ((j.get("data") or {}).get("list")) or []
            if isinstance(lst, list) and len(lst) > len(rows):
                rows = lst
        except Exception as e:
            logf(f"重放 findPage 失败: {str(e)[:70]}")

    seen = set()
    units = []
    for a in rows:
        aid = str(a.get("adgroupId"))
        if aid and aid != "None" and aid not in seen:
            seen.add(aid)
            units.append({"adgroupId": aid, "adgroupName": a.get("adgroupName")})
    return units


async def goto_unit(page, campaign_id, adgroup_id, day, logf):
    url = SEARCH_DETAIL.format(cid=campaign_id, d=day) + f"&adgroupId={adgroup_id}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        logf(f"单元页 goto 异常: {str(e)[:70]}")
    for _ in range(20):
        await asyncio.sleep(1.0)
        kws = await page.evaluate(READ_KEYWORDS_JS)
        if kws:
            return kws
    return []


def word_from_hash(hash_url):
    """从流量解析 hash URL 里还原搜索词（词是双重 URL 编码，见 build_traffic_hash/关键词锚点）。"""
    m = re.search(r"[?&]word=([^&]+)", hash_url)
    if not m:
        return ""
    try:
        return unquote(unquote(m.group(1)))
    except Exception:
        return ""


FILL_SEARCH_JS = r"""(word) => {
  const vis = e => !!(e.offsetWidth || e.offsetHeight);
  const inp = [...document.querySelectorAll('input')]
    .find(e => vis(e) && e.type === 'text' && (e.placeholder || '').includes('请输入关键词'));
  if (!inp) return 'no_input';
  // React 受控输入：原生 setter + input/change 事件
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, word);
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  inp.dispatchEvent(new Event('change', { bubbles: true }));
  return 'filled';
}"""

CLICK_QUERY_JS = r"""() => {
  const vis = e => !!(e.offsetWidth || e.offsetHeight);
  const btn = [...document.querySelectorAll('button')]
    .find(e => vis(e) && (e.innerText || '').replace(/\s+/g, '').trim() === '查询');
  if (!btn) return false;
  btn.click();
  return true;
}"""

CLICK_TAB_JS = r"""() => {
  const t=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
  const el=[...document.querySelectorAll('*')].find(e=>t(e)==='竞争流量透视');
  if(el){ el.click(); return true; } return false;
}"""


async def _swap_and_query(page, word):
    """页内替换搜索词并点「查询」（零整页刷新）。返回 'ok'/'no_input'/'no_fresh'。"""
    filled = await page.evaluate(FILL_SEARCH_JS, word)
    if filled != "filled":
        return "no_input"
    loop = asyncio.get_event_loop()
    fresh = loop.create_future()
    want = json.dumps(word, ensure_ascii=False)   # 带引号匹配 post_data，避免子串误命中

    def on_resp(r):
        if fresh.done() or r.request.method != "POST":
            return
        if "triggerDynamicModule.json" not in r.url:
            return
        try:
            post = r.request.post_data or ""
        except Exception:
            return
        if want in post:
            fresh.set_result(True)

    page.on("response", on_resp)
    try:
        clicked = await page.evaluate(CLICK_QUERY_JS)
        if not clicked:
            return "no_input"
        try:
            await asyncio.wait_for(fresh, timeout=8)
        except asyncio.TimeoutError:
            return "no_fresh"
    finally:
        try:
            page.remove_listener("response", on_resp)
        except Exception:
            pass
    return "ok"


def _walk_pv_rows(node, out):
    """递归收集含 pvName+avgPrice 的节点（1468 响应里的流量来源行）。"""
    if isinstance(node, dict):
        if "pvName" in node and "avgPrice" in node:
            out.append(node)
        for v in node.values():
            _walk_pv_rows(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_pv_rows(v, out)


def shou_avg_from_body(body):
    """从 1468 响应体取「手淘」市场均价（pvtypeId=1），按展示口径 round 到分。取不到返回 None。"""
    rows = []
    _walk_pv_rows(body, rows)
    for r in rows:
        if r.get("pvName") == "手淘" or r.get("pvtypeId") == 1:
            try:
                return round(float(r["avgPrice"]), 2)
            except Exception:
                pass
    return None


async def _market_avg_api(page, word, logf):
    """页内换词查询，等「请求含该词」的 1468（过去7天日均）响应并从 body 解析手淘均价。

    响应与请求一一对应 → 无渲染竞态（2026-10-17 修复：旧页内路读 DOM 表格，
    表格渲染慢于接口，部分词读到上一个词的均价）。
    返回 (data dict 或 None, 原因 'ok'/'no_input'/'no_data')。
    """
    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    want = json.dumps(word, ensure_ascii=False)

    async def on_resp(r):
        if fut.done() or r.request.method != "POST":
            return
        if "triggerDynamicModule.json" not in r.url:
            return
        try:
            post = r.request.post_data or ""
            if want not in post:
                return
            req = json.loads(post)
            if str(req.get("moduleId")) != "1468":
                return
            body = json.loads(await r.text())
        except Exception:
            return
        price = shou_avg_from_body(body)
        if price is not None:
            fut.set_result(price)

    page.on("response", on_resp)
    try:
        filled = await page.evaluate(FILL_SEARCH_JS, word)
        if filled != "filled":
            return None, "no_input"
        clicked = await page.evaluate(CLICK_QUERY_JS)
        if not clicked:
            return None, "no_input"
        try:
            price = await asyncio.wait_for(fut, timeout=12)
        except asyncio.TimeoutError:
            return None, "no_data"
    finally:
        try:
            page.remove_listener("response", on_resp)
        except Exception:
            pass
    return {"source": "手淘", "price": price}, "ok"


async def market_avg(page, hash_url, source, logf):
    """在固定复用的流量解析页上读指定来源市场均价。

    2026-10-17 起页内换词 + 从 1468 响应体解析手淘 avgPrice（无竞态，零整页重载——
    反复整页刷新流量解析易触发滑块）。页内路不可用（首次加载/找不到搜索框）才回退
    老路 about:blank→goto 整页重载 + DOM 读表。查不到均价返回 None（调用方记 skip_no_market）。
    """
    word = word_from_hash(hash_url)
    if word:
        try:
            res, why = await _market_avg_api(page, word, logf)
        except Exception as e:
            res, why = None, f"err:{str(e)[:50]}"
            logf(f"页内查价异常: {why}")
        if res:
            return res
        if why == "no_data":
            return None          # 查询确已发生、响应已解析，只是没有手淘行
        # no_input/err → 走老路
    # 老路兜底：该页 URL 只有 hash 不同 → goto 属同文档导航，SPA 可能不重渲染而
    # 读到上一个词的表。先 about:blank 再 goto 目标，强制整页新加载。
    try:
        await page.goto("about:blank", wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass
    try:
        await page.goto(hash_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        logf(f"流量解析 goto 异常: {str(e)[:60]}")
    for _ in range(32):                      # 轮询 tab 出现，最长 ~10s
        await asyncio.sleep(0.3)
        clicked = await page.evaluate(CLICK_TAB_JS)
        if clicked:
            break
    for _ in range(20):                      # 轮询数据出现，最长 ~6s
        await asyncio.sleep(0.3)
        data = await page.evaluate(READ_MARKET_JS)
        if data and data.get("price"):
            return data
    return None


# ---------------- 写入 ----------------

async def set_bid(page, bidword_id, value, logf):
    """在搜索详情页把某词的出价改为 value。返回 (ok, msg)。"""
    opened = await page.evaluate(r"""(kwid) => {
      const cell=document.querySelector('#bidword_'+kwid+'_price'); if(!cell) return 'no cell';
      const i=cell.closest('td').querySelector('i[mx-click*="editPrice"]'); if(!i) return 'no icon';
      i.click(); return 'opened';
    }""", bidword_id)
    if opened != "opened":
        return False, opened
    # 等弹框（短轮询，最长 ~3s）
    has = False
    for _ in range(12):
        await asyncio.sleep(0.25)
        has = await page.evaluate(r"""() => !!document.querySelector('input[mxc*="customPrice"]')""")
        if has:
            break
    if not has:
        await page.evaluate(r"""() => {
          const t=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
          const d=[...document.querySelectorAll('div')].filter(e=>e.offsetParent!==null)
            .filter(e=>{const s=t(e);return s.includes('手动出价')&&s.includes('取消');})
            .sort((a,b)=>t(a).length-t(b).length)[0];
          if(d){const c=[...d.querySelectorAll('button,a,[mx-click]')].find(e=>t(e)==='取消'); if(c)c.click();}
        }""")
        return False, "no_dialog"
    # 选“手动出价”并填值（一次 evaluate 完成）
    await page.evaluate(r"""(v) => {
      const r=document.querySelector('input[name="price"][value="-1"]'); if(r) r.click();
      const inp=document.querySelector('input[mxc*="customPrice"]');
      if(inp){ inp.disabled=false; inp.focus(); inp.value=v;
        inp.dispatchEvent(new Event('input',{bubbles:true}));
        inp.dispatchEvent(new Event('change',{bubbles:true})); }
    }""", str(value))
    await asyncio.sleep(0.3)
    conf = await page.evaluate(r"""() => {
      const t=e=>(e.innerText||'').replace(/\s+/g,' ').trim();
      const d=[...document.querySelectorAll('div')].filter(e=>e.offsetParent!==null)
        .filter(e=>{const s=t(e);return s.includes('手动出价')&&s.includes('确定');})
        .sort((a,b)=>t(a).length-t(b).length)[0];
      if(!d) return 'no dlg';
      const btn=[...d.querySelectorAll('button')].find(e=>t(e)==='确定'); if(!btn) return 'no btn';
      btn.click(); return 'confirmed';
    }""")
    if conf != "confirmed":
        return False, f"confirm:{conf}"
    # 回读校验（轮询，最长 ~4s）
    now = ""
    for _ in range(14):
        await asyncio.sleep(0.3)
        now = await page.evaluate(r"""(kwid) => {
          const s=document.querySelector('#bidword_'+kwid+'_bid_price');
          return s? (s.innerText||'').replace(/\s+/g,' ').trim() : '';
        }""", bidword_id)
        if str(value) in now:
            return True, f"readback={now}"
    return False, f"readback={now}"


# ---------------- 主流程 ----------------

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


def record(rep, item):
    """按 bidwordId 就地更新，避免重复跑时同一词堆多行。"""
    for i, old in enumerate(rep["items"]):
        if old.get("bidwordId") == item["bidwordId"]:
            rep["items"][i] = item
            return
    rep["items"].append(item)


async def run(args):
    day = date.today().isoformat()
    rep = load_report(args.report)
    # --force：忽略历史 ok，整轮重算（市场均价/人群溢价变化后重新调价时用）
    done_ok = set() if args.force else \
        {i["bidwordId"] for i in rep["items"] if i.get("status") == "ok"}
    log(f"计划 {args.campaign_id} | 溢价{args.premium}% 折扣{args.discount}% 来源={args.source} "
        f"| {'DRY-RUN' if args.dry_run else 'APPLY'}{' FORCE' if args.force else ''} | 已 ok {len(done_ok)}")

    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    processed = 0
    market_cache = {}
    no_market_streak = 0
    mkt_page = None
    try:
        # 整轮只用 2 个标签：1 个搜索详情页 + 1 个流量解析页
        page = next((p for p in ctx.pages if "search-detail" in p.url), None)
        if page is None:
            page = await ctx.new_page()
        for p in list(ctx.pages):
            if p is not page:
                try:
                    await p.close()
                except Exception:
                    pass
        units = await open_units_page(ctx, args.campaign_id, day, log, page)
        if not units:
            log("!! 没抓到单元列表（登录态掉了？）")
            return 2
        if args.adgroup_id:
            want = set(args.adgroup_id.split(","))
            units = [u for u in units if u["adgroupId"] in want]
        log(f"待处理单元 {len(units)} 个")
        mkt_page = await ctx.new_page()

        for ui, u in enumerate(units, 1):
            kws = await goto_unit(page, args.campaign_id, u["adgroupId"], day, log)
            log(f"[{ui}/{len(units)}] 单元 {u['adgroupId']} {u['adgroupName'][:24]} → {len(kws)} 词")
            for kw in kws:
                if args.limit and processed >= args.limit:
                    log(f"已达 --limit {args.limit}，停止")
                    return 0
                if kw["bidwordId"] in done_ok:
                    continue
                word = kw["word"]
                if word in market_cache:
                    market = market_cache[word]
                else:
                    market = await market_avg(mkt_page, TRAFFIC.format(hash=kw["href"]), args.source, log)
                    market_cache[word] = market
                if not market or not market.get("price"):
                    no_market_streak += 1
                    log(f"    · {kw['word']} 无「{args.source}」市场均价，跳过")
                    record(rep, {"bidwordId": kw["bidwordId"], "word": kw["word"],
                                 "adgroupId": u["adgroupId"], "status": "skip_no_market"})
                    save_report(args.report, rep)
                    processed += 1
                    if no_market_streak >= 8:
                        log("!! 连续 8 次取不到市场均价，疑似登录态/风控，停止本轮")
                        return 4
                    await asyncio.sleep(args.gap)
                    continue
                no_market_streak = 0
                newbid = calc_bid(market["price"], args.premium, args.discount, args.min_bid)
                if args.dry_run:
                    log(f"    · {kw['word']} 市场均价={market['price']} → 出价={newbid} (dry)")
                    record(rep, {"bidwordId": kw["bidwordId"], "word": kw["word"],
                                 "adgroupId": u["adgroupId"], "market": market["price"],
                                 "newBid": newbid, "status": "dry"})
                else:
                    ok, msg = await set_bid(page, kw["bidwordId"], newbid, log)
                    log(f"    · {kw['word']} 市场均价={market['price']} → {newbid} {'OK' if ok else 'FAIL'} {msg}")
                    record(rep, {"bidwordId": kw["bidwordId"], "word": kw["word"],
                                 "adgroupId": u["adgroupId"], "market": market["price"],
                                 "newBid": newbid, "status": "ok" if ok else "fail", "note": msg})
                    if not ok:
                        # 风控/验证码迹象直接停，保留现场
                        if any(x in str(msg) for x in ("no_dialog", "confirm:no btn")):
                            save_report(args.report, rep)
                            log("!! 写入异常，停止本轮（先查现场）")
                            return 3
                save_report(args.report, rep)
                processed += 1
                await asyncio.sleep(args.gap)
        log(f"完成：本轮处理 {processed} 个词，报告 {args.report}")
        return 0
    finally:
        try:
            await b.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign-id", default="83392643008")
    ap.add_argument("--adgroup-id", default=None, help="逗号分隔；不给=该计划所有单元")
    ap.add_argument("--premium", type=float, default=300)
    ap.add_argument("--discount", type=float, default=35)
    ap.add_argument("--source", default="手淘")
    ap.add_argument("--min-bid", type=float, default=0.05)
    ap.add_argument("--gap", type=float, default=5.0, help="词与词之间间隔秒数")
    ap.add_argument("--limit", type=int, default=0, help="本轮最多处理多少词")
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--force", action="store_true",
                    help="忽略历史 ok，整轮重算（市场均价/人群溢价变化后重新调价时用）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="只读+打印，不写")
    g.add_argument("--apply", action="store_true", help="真正写入")
    a = ap.parse_args()
    if not a.apply:
        a.dry_run = True
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
