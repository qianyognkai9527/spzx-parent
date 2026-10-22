#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集淘宝「已卖出宝贝」订单 → order_info + order_item (platform_type=1)。

只读: 只翻页/打字设条件, 绝不点任何写按钮。
跑法:
  automation/venv/bin/python tb-auto/collect_taobao_trade.py --dry-run --limit 5
  # 历史段由 --from + --hist-end(默认 --split);「近3个月」视图单独采。
  automation/venv/bin/python tb-auto/collect_taobao_trade.py --from 2024-10-01 --hist-end 2026-07-14
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import (build_order_info_row, build_order_item_row, connect_db,  # noqa: E402
                        log, parse_sold_cells, quarter_windows, upsert_order_info,
                        upsert_order_item)

PORT = 9222
SOLD = "https://myseller.taobao.com/home.htm/trade-platform/tp/sold"
PROGRESS = os.path.join(BASE, "taobao_trade_progress.json")

EXTRACT_JS = r"""() => {
  const trs=[...document.querySelectorAll('table tbody tr')].filter(tr=>(tr.innerText||'').trim());
  return trs.map(tr=>({
    cells:[...tr.querySelectorAll('td')].map(td=>(td.innerText||'').trim()),
    raw:(tr.innerText||'').replace(/\n+/g,' / ')
  }));
}"""


def read_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            pg = json.load(f)
    else:
        pg = {}
    pg.setdefault("done_windows", [])
    pg.setdefault("near_done", False)
    return pg


def save_progress(pg):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(pg, f, ensure_ascii=False, indent=2)


async def dismiss_overlays(p):
    for _ in range(3):
        if not await p.evaluate("() => !!document.querySelector('.next-overlay-wrapper.opened')"):
            return
        await p.keyboard.press("Escape")
        await p.wait_for_timeout(400)


async def _fill_date(loc, value):
    """真实键盘输入覆盖, 不用 fill(): 日期面板二次打开时 fill() 只改 DOM 文本、
    不写面板内部已选日期, Enter 会把上一次的起始日重新提交(窗口越滚越大)。"""
    await loc.click()
    await loc.press("Meta+A")
    await loc.press("Backspace")
    await loc.type(value, delay=30)


async def _apply_range(p, start, end):
    await dismiss_overlays(p)
    await p.locator('input[placeholder="起始日期"]').first.click()
    await p.wait_for_timeout(1200)
    s = p.locator('.next-range-picker-panel-input-start-date input')
    e = p.locator('.next-range-picker-panel-input-end-date input')
    await _fill_date(s, start); await p.wait_for_timeout(400)
    await _fill_date(e, end); await p.wait_for_timeout(400)
    await p.keyboard.press("Enter"); await p.wait_for_timeout(1000)
    await dismiss_overlays(p)


async def set_range(p, start, end):
    """设日期区间 + 搜索订单。返回 True 仅当 start/end 两个输入框都验证为期望值。"""
    ok = False
    for attempt in range(2):
        await _apply_range(p, start, end)
        got_s = await p.locator('input[placeholder="起始日期"]').first.input_value()
        got_e = await p.locator('input[placeholder="结束日期"]').first.input_value()
        if got_s.startswith(start) and got_e.startswith(end):
            ok = True
            break
        log(f"  日期未回填 start={got_s!r}/{start} end={got_e!r}/{end}, 重试({attempt + 1})")
    btns = p.locator('button', has_text="搜索订单")
    await btns.nth(await btns.count() - 1).click()
    await p.wait_for_timeout(5000)
    return ok


async def next_page(p):
    for sel in ('button:has-text("下一页")', '.next-pagination-next button'):
        loc = p.locator(sel).first
        if await loc.count():
            # Next UI 把禁用态放在祖先 <li class="...disabled...">, 按钮本身无 disabled。
            disabled = await loc.evaluate(
                "e => { const li = e.closest('li'); "
                "return !!(li && li.className.includes('disabled')) || !!e.disabled; }")
            if disabled:
                return False
            await loc.click()
            await p.wait_for_timeout(4000)
            return True
    return False


def parse_page(rows):
    """淘宝已卖出宝贝每单拆成两行: 订单头行(1 td: 订单号/创建时间/买家) + 商品行(7 td)。

    parse_sold_cells 期望**单行 8 列**布局 ([checkbox, 头, 商品, 单价, 数量, 售后, 交易, 实收]),
    故这里把 头行 + 商品行 合并并在最前补空格模拟 checkbox 列。多商品订单头行会延续,
    每商品行各产出一条 (order_item 幂等键 (order_id, sku_name))。
    """
    out = []
    head = None
    for r in rows:
        cells = list(r.get("cells") or [])
        if not cells:
            continue
        if len(cells) < 7 and any("订单号" in (c or "") for c in cells):
            head = cells
            continue
        if head is not None and len(cells) >= 7:
            # 履约/售后(3) 与 交易状态(4) 单元格混着操作按钮文案(打单/发货/寄件…),
            # 只保留首行真状态, 否则 map_trade_status 会被按钮文案干扰。
            clean = list(cells)
            for i in (3, 4):
                first = [ln.strip() for ln in (clean[i] or "").splitlines() if ln.strip()]
                clean[i] = first[0] if first else ""
            parsed = parse_sold_cells([""] + head + clean)
            if parsed:
                parsed["_raw"] = r.get("raw")
                out.append(parsed)
    return out


async def collect_segment(p, conn, shop_id, tag, args, start=None, end=None):
    """翻完当前视图所有页, 落库。rows_total 计数返回 (rows, pages)。

    每 10 页整页重载并重建现场(设区间+搜索+跳回本页): 淘宝页 SPA 重, 长翻页会 Target crashed。
    """
    page = 1
    total = 0
    while page <= args.max_pages:
        if page > 1 and (page - 1) % 10 == 0 and start and end:
            log(f"  {tag} 第{page}页前重载防崩…")
            await p.reload(wait_until="domcontentloaded", timeout=60000)
            await p.wait_for_timeout(9000)
            await dismiss_overlays(p)
            if not await set_range(p, start, end):
                log(f"  {tag} 重载后区间未确认, 结束本段")
                break
            for _ in range(page - 1):
                if not await next_page(p):
                    break
                await p.wait_for_timeout(300)
        rows = await p.evaluate(EXTRACT_JS)
        parsed = parse_page(rows)
        if not parsed:
            break
        if args.dry_run:
            for x in parsed:
                if args.limit and total >= args.limit:
                    break
                log(f"  [dry] {x['order_no']} {x['create_time']} ¥{x['real_pay']} "
                    f"{x['trade_status']} {x['after_sale_status']} | {x['title']}")
                total += 1
        else:
            n = 0
            for x in parsed:
                oid = upsert_order_info(conn, build_order_info_row(x, shop_id))
                upsert_order_item(conn, oid, build_order_item_row(x))
                n += 1
            conn.commit()
            total += n
        log(f"{tag} 第{page}页: {len(parsed)} 行")
        if args.limit and total >= args.limit:
            break
        if not await next_page(p):
            break
        page += 1
    return total


async def run(args):
    hist_end = args.hist_end or args.split
    windows = quarter_windows(args.dfrom, hist_end)
    if not windows:
        log(f"历史窗口为空: {args.dfrom} ~ {hist_end}")
    b, ctx = await connect_cdp(PORT, keep_urls=["myseller.taobao.com", "taobao.com", "ufuwu.1688.com"], log=log)
    conn = None if args.dry_run else connect_db()
    pg = read_progress()
    try:
        p = None
        try:
            p = await ctx.new_page()
            cur = None
            if not args.dry_run:
                with conn.cursor() as c:
                    from shop_ref import default_shop_id, PLATFORM_TAOBAO
                    cur = default_shop_id(c, PLATFORM_TAOBAO)
            await p.goto(SOLD, wait_until="domcontentloaded", timeout=60000)
            await p.wait_for_timeout(9000)
            await p.evaluate("() => { const e=[...document.querySelectorAll('li')]"
                             ".find(x=>(x.innerText||'').trim()==='3个月前'); if(e)e.click(); }")
            await p.wait_for_timeout(6000)
            for start, end in windows:
                key = f"{start}~{end}"
                if key in pg["done_windows"] and not args.force:
                    log(f"跳过已完成窗口 {key}")
                    continue
                if not await set_range(p, start, end):
                    log(f"警告: 窗口 {key} 起始/结束日期未确认, 跳过落库且**不标记完成**"
                        f" (下次重跑会重试)")
                    continue
                await collect_segment(p, conn, cur, f"历史 {key}", args, start, end)
                if not args.dry_run:
                    pg["done_windows"].append(key); save_progress(pg)
            if not pg.get("near_done") or args.force:
                await p.evaluate("() => { const e=[...document.querySelectorAll('li')]"
                                 ".find(x=>(x.innerText||'').trim()==='近3个月'); if(e)e.click(); }")
                await p.wait_for_timeout(6000)
                await collect_segment(p, conn, cur, "近3个月", args)
                if not args.dry_run:
                    pg["near_done"] = True; save_progress(pg)
        finally:
            if p is not None:
                await p.close()
    finally:
        if conn:
            conn.close()
        await b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--split", dest="split",
                    default=(date.today() - timedelta(days=90)).isoformat(),
                    help="历史/近期视图分界日")
    ap.add_argument("--hist-end", default=None, help="历史段截止(默认=split)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="忽略进度重跑")
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
