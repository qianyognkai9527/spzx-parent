#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISV「商品管理」采集: (淘宝 itemId, 1688 offerId) -> isv_offer_taobao_map.jsonl.

数据源(2026-10-01 用户指正): ISV「商品管理」表一行同时含 店铺商品ID(淘宝 itemId) 与
货源商品ID(1688 offerId) —— 不开新标签、无需点击。

⚠ 2026-10-14 重采发现:
- 旧档 994 对是默认关键词「甲」筛出来的、**不是全量** —— 不含"甲"的铺货商品
  (外套/派克服等)全漏, 对 2026 采购 offer 命中 0/119。
- ISV 后台已改版 v3.5.51: 侧栏收起 + 菜单重组, 「商品管理」挪到 分销铺货 flyout;
  收起态下 JS click 与 Playwright 常规 hover 均失效, 须 force hover + 真点击。
- 商品管理比"销售中"视图大: 快捷筛选 销售中(995)/仓库中(3183)/**已关联货源(4173)**;
  完整映射集 = 已关联货源 chip(销售中+仓库中)。
- **SPA 筛选 chip 跨会话残留**(残留货源ID筛选曾把 --ids 查询毒成 0 行) → 每次先点「重置」。
- 货源ID 精查输入框支持逗号分隔最多100条 → --offers 按 50/批批量查, 个别行行内
  不渲染货源ID文本 → ROWS_JS 回退从 a[href*=detail.1688.com/offer/] 提取。

写文件为**合并写**: 读现有 jsonl 按 taobao_item_id 建 dict, 本次结果 update 进去
(同 id 新行覆盖旧行), 排序写回 —— 不丢已删商品的旧对。

前置: 9222 已登录 1688。
跑法:
  automation/venv/bin/python scrape_isv_offer_taobao.py --ids 1077395263073,1080310116827
  automation/venv/bin/python scrape_isv_offer_taobao.py            # 全量(空关键词, 翻页)
  automation/venv/bin/python scrape_isv_offer_taobao.py --keyword 外套   # 定向关键词
  automation/venv/bin/python scrape_isv_offer_taobao.py --offers 846834016457,742890863978
"""
import argparse
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_utils import connect_cdp  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isv_offer_taobao_map.jsonl")
ISV_URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"

ROWS_JS = r"""() => {
  return [...document.querySelectorAll('tr')].map(tr => {
    const ids = [...(tr.innerText||'').matchAll(/ID：(\d+)/g)].map(m => m[1]);
    if (!ids.length) return null;
    const a = tr.querySelector('a[href*="detail.1688.com/offer/"]');
    const hm = a ? (a.getAttribute('href')||'').match(/offer\/(\d+)/) : null;
    const t = (tr.innerText||'').replace(/\s+/g,' ').trim();
    return {taobao_item_id: ids[0], offer_id: ids[1] || (hm ? hm[1] : null), text: t};
  }).filter(Boolean);
}"""

CLICK_QUERY_JS = r"""() => { const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').replace(/\s/g,'')==='查询'); if(b)b.click(); }"""
CLICK_RESET_JS = r"""() => { const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').replace(/\s/g,'')==='重置'); if(b)b.click(); }"""
CLICK_TAB_JS = r"""(t) => { const e=[...document.querySelectorAll('*')].find(x=>(x.children.length===0)&&(x.textContent||'').trim()===t); if(e)e.click(); }"""
# 输入框多在「更多」折叠后 visible=False, Playwright fill 拒填隐藏元素(踩过: 3个sid批量查
# 全没生效, 抓回整tab 991行) —— 必须用原生 setter + input 事件绕过可见性(React 受控输入实测有效)。
SET_INPUTS_JS = r"""(kv) => { for (const [sel, val] of kv) { const i=document.querySelector(sel); if(!i) continue; const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, val); i.dispatchEvent(new Event('input', {bubbles:true})); } }"""


async def get_frame(page):
    for _ in range(20):
        await asyncio.sleep(1)
        fr = [f for f in page.frames if "isv-container" in f.url]
        if fr:
            return fr[0]
    return None


async def open_page(ctx, quiet=False):
    for p in ctx.pages:
        if "fuwu_work_isv_container" in p.url:
            return p
    p = await ctx.new_page()
    if quiet:
        from cdp_utils import minimize_windows
        try:
            await minimize_windows(ctx)
        except Exception:
            pass
    await p.goto(ISV_URL, wait_until="domcontentloaded", timeout=40000)
    await asyncio.sleep(7)
    if quiet:
        from cdp_utils import minimize_windows
        try:
            await minimize_windows(ctx)
        except Exception:
            pass
    return p


async def nav_to_guanli(fr):
    """新 UI(v3.5.51): 收起侧栏 → force hover 分销铺货 → 真点击 flyout 里的 商品管理。"""
    try:
        await (fr.locator("li.ant-menu-submenu", has_text="分销铺货")
               .locator(".ant-menu-submenu-title").first.hover(force=True, timeout=6000))
        await asyncio.sleep(2)
        await fr.locator(".ant-menu-submenu-popup .ant-menu-item", has_text="商品管理").first.click(timeout=5000)
    except Exception as e:
        print(f"新UI导航失败({str(e)[:60]}), 回退旧版 leaf-text click")
        await fr.evaluate("""() => { const e=[...document.querySelectorAll('*')].find(x=>(x.children.length===0)&&(x.textContent||'').trim()==='商品管理'); if(e)e.click(); }""")
    await asyncio.sleep(6)


async def fill_fast(fr, sel, val):
    try:
        await fr.locator(sel).fill(val, timeout=2500)
        return True
    except Exception:
        return False


async def select_tab(fr, name="已关联货源"):
    """快捷筛选 chip: 已关联货源 = 全部带货源映射的商品(销售中+仓库中, 新UI实测4173)。
    SPA 筛选 chip 会跨会话残留(踩过: 残留货源ID筛选把 --ids 查询毒成 0 行), 先重置再选。"""
    await fr.evaluate(CLICK_RESET_JS)
    await asyncio.sleep(2)
    await fr.evaluate(CLICK_TAB_JS, name)
    await asyncio.sleep(3)


async def query(fr, search_key="", source_ids="", shop_ids=""):
    await fr.evaluate(SET_INPUTS_JS, [
        ["input#shopProductIds", shop_ids or ""],
        ["input#sourceProductIds", source_ids or ""],
        ["input#searchKey", search_key or ""],
    ])
    await asyncio.sleep(1)
    await fr.evaluate(CLICK_QUERY_JS)
    await asyncio.sleep(5)


def read_total(body_text):
    m = re.search(r"共\s*([\d,]+)\s*条", body_text)
    return int(m.group(1).replace(",", "")) if m else 0


async def click_page(fr, pg):
    await fr.evaluate("""(p) => { const ns=[...document.querySelectorAll('[class*=pagination] *,[class*=Pagination] *')]; const e=ns.find(x=>(x.textContent||'').trim()===String(p)); if(e)e.click(); }""", pg)


async def click_next(fr):
    try:
        await fr.locator(".ant-pagination-next").first.click(timeout=2500, force=True)
        return True
    except Exception:
        return False


def load_existing(path):
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("taobao_item_id"):
                    out[str(r["taobao_item_id"])] = r
    return out


def write_merged(path, fresh):
    merged = load_existing(path)
    for r in fresh:
        merged[str(r["taobao_item_id"])] = r
    with open(path, "w", encoding="utf-8") as f:
        for k in sorted(merged):
            f.write(json.dumps(merged[k], ensure_ascii=False) + "\n")
    return len(merged)


async def scrape_paged(fr, result, label):
    """当前查询条件下逐页抓, 行 append 进 result。"""
    body = await fr.inner_text("body")
    total = read_total(body)
    pages = (total + 19) // 20 if total else 1
    print(f"[{label}] 命中 {total} 条, {pages} 页")
    prev_first = None
    for pg in range(1, pages + 1):
        if pg > 1:
            await click_page(fr, pg)
            await asyncio.sleep(3)
            body2 = await fr.inner_text("body")
            if not read_total(body2):
                await click_next(fr)
                await asyncio.sleep(3)
        rows = await fr.evaluate(ROWS_JS)
        if rows and prev_first and rows[0]["taobao_item_id"] == prev_first:
            print(f"[{label}] 第{pg}页首行未变化, 中止防死循环")
            break
        if rows:
            prev_first = rows[0]["taobao_item_id"]
        for r in rows:
            result.append(r)
            print(f"  {r['taobao_item_id']} -> {r['offer_id']}")
        if total and pg * 20 >= total:
            break


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="", help="逗号分隔的店铺商品ID(淘宝 itemId), 精查")
    ap.add_argument("--offers", default="", help="逗号分隔的1688货源ID, 按货源ID精查(自动按50/批; 行内offer缺失时回退href提取)")
    ap.add_argument("--keyword", default="", help="标题关键词筛选; 默认空=全量(旧版默认'甲'会漏非甲商品, 勿改回)")
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()

    b, ctx = await connect_cdp(9222, keep_urls=["fuwu_work_isv_container", "isv-container",
                                                "1688.com", "item.upload.taobao.com", "myseller.taobao.com"], log=print)
    page = await open_page(ctx)
    result = []
    try:
        fr = await get_frame(page)
        await nav_to_guanli(fr)
        await select_tab(fr)
        if args.ids:
            if not await fill_fast(fr, "input#shopProductIds", args.ids):
                print("input#shopProductIds 不存在(新UI?), 改用 searchKey 试")
                await fill_fast(fr, "input#searchKey", args.ids)
            await fr.evaluate(CLICK_QUERY_JS)
            await asyncio.sleep(5)
            rows = await fr.evaluate(ROWS_JS)
            for r in rows:
                result.append(r)
                print(f"  {r['taobao_item_id']} -> {r['offer_id']}")
        elif args.offers:
            sids = [s.strip() for s in args.offers.split(",") if s.strip()]
            covered = {str(r["offer_id"]) for r in load_existing(OUT).values() if r.get("offer_id")}
            for i in range(0, len(sids), 50):
                chunk = sids[i:i + 50]
                before = len(result)
                await query(fr, source_ids=",".join(chunk))
                await scrape_paged(fr, result, f"offers[{i}+{len(chunk)}]")
                got = result[before:]
                covered |= {r["offer_id"] for r in got if r["offer_id"]}
                print(f"  批 {i}~{i + len(chunk) - 1}: +{len(got)} 行")
                if got:
                    print("WROTE", OUT, f"增量合并后 {write_merged(OUT, got)} 行")
            # 行内/href 都没渲染货源ID的行(常见于 关联货源已下架) → 单sid补查, 唯一行以sid归属
            missing = [s for s in sids if s not in covered]
            print(f"单sid补查 {len(missing)} 个(批查未覆盖)")
            for sid in missing:
                await query(fr, source_ids=sid)
                rows = await fr.evaluate(ROWS_JS)
                if not rows:
                    print(f"  {sid}: 共0条(从未铺货/已删/无关联, 无映射)")
                    continue
                take = []
                for r in rows:
                    if r["offer_id"]:
                        take.append(r)
                    else:
                        take.append({"taobao_item_id": r["taobao_item_id"], "offer_id": sid,
                                     "title": r["text"], "src": "single-sid"})
                        print(f"  {sid} -> {r['taobao_item_id']} (行内无货源ID, 以sid归属)")
                if len(rows) > 1:
                    print(f"  ⚠ {sid}: 命中 {len(rows)} 行, 非唯一, 仅无offer行以sid归属")
                result.extend(take)
                print("WROTE", OUT, f"增量合并后 {write_merged(OUT, take)} 行")
        else:
            await query(fr, search_key=args.keyword)
            await scrape_paged(fr, result, "全量" if not args.keyword else f"kw={args.keyword}")
            if args.max:
                result = result[: args.max]
        n = write_merged(OUT, result)
        print("WROTE", OUT, f"合并后 {n} 行(本次抓 {len(result)}, 含offerId: {sum(1 for r in result if r['offer_id'])})")
    finally:
        try:
            await b.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
