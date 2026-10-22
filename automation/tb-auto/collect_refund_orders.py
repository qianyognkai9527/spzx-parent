#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集淘宝「退款管理」售后/退款记录 → refund_order, 并派生 refund_import_order。

只读: 只点 售后类型 tab / 退款时间(最近申请/历史退款) / 日期 / 搜索售后单 / 翻页。
绝不点 同意退款/同意退货/备注/导出/智能退款工具/一键开通极速售后。

实地观测(2026-10-12):
  - 页面被 driver.js 新手引导浮层(`.driver-overlay`/`.driver-popover`)拦截点击 → 先移除；
  - 退款时间 scope 下拉默认「最近申请」(只看近几天, 忽略日期查询) → 历史查询必须切「历史退款」；
  - 列表行不是普通 `table tbody tr`, 而是每条售后一张 `table.next-table-row`,
    内含 2 个 `tbody > tr`: `tr.next-table-group-header`(订单号/退款编号/申请时间/买家) +
    普通 tr(5 个 td: 商品信息|金额信息|原因件数|售后状态|操作)；
  - 日期区间输入在 `.next-range-picker-body` 面板里, 用
    `.next-range-picker-panel-input-start-date input` / `-end-date input` 填。

保留期(2026-10-12 实测): 页面可查询到约 2023-07-01; 2023Q2 及更早返回空。默认 `--from`
因此取 `RETENTION_START=2023-07-01`(覆盖全部可回溯范围, 取代设计稿原定的 2024-10-01)。

跑法:
  automation/venv/bin/python tb-auto/collect_refund_orders.py --dry-run --limit 5 \\
      --from 2025-01-01 --to 2025-03-31
  automation/venv/bin/python tb-auto/collect_refund_orders.py
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import connect_db, log, quarter_windows  # noqa: E402
from refund_common import (DERIVED_CODE, build_refund_row, ensure_auto_report,  # noqa: E402
                           refresh_derived_import_orders, upsert_refund_order)
from shop_ref import PLATFORM_TAOBAO, default_shop_id  # noqa: E402

PORT = 9222
URL = "https://myseller.taobao.com/home.htm/trade-platform/refund-list"
PROGRESS = os.path.join(BASE, "refund_progress.json")

# 退款页实测保留起点(2023-07-01 起可查, 2023Q2 及更早为空) → 默认 --from 覆盖全保留范围
RETENTION_START = "2023-07-01"

# 售后类型 tab 文本(driver.js 引导层按钮里也有同名文本, 故用 li.next-tabs-tab 精确匹配)
TYPES = ["未发货退款", "未收货退款", "已收货退款", "退货退款", "维修", "换货", "补寄", "退运费"]


class StructuralError(RuntimeError):
    """页面结构异常(如一个售后类型 tab 都没有) → 视为风控/结构失败, 非 0 退出。"""


def month_windows(dfrom, dto, months):
    """按 N 个自然月切窗(末端被 dto 截断)。比季度窗少一半固定开销。"""
    start = datetime.strptime(dfrom, "%Y-%m-%d").date()
    end = datetime.strptime(dto, "%Y-%m-%d").date()
    out, cur = [], start
    while cur <= end:
        nxt = date(cur.year + (cur.month - 1 + months) // 12,
                   (cur.month - 1 + months) % 12 + 1, 1)
        w_end = min(nxt - timedelta(days=1), end)
        out.append((cur.isoformat(), w_end.isoformat()))
        cur = nxt
    return out


# 每条售后 = 一张 `table.next-table-row`; 列表容器本身也可能是 table, 故先定位含
# 「商品信息」表头的网格容器, 且只取**自身无 thead** 的 next-table-row(排除表头/容器表)。
# header tr 含 订单号/退款编号/申请时间/买家, 普通 tr 含 5 个 td; title/sku 取 col0 的 a[title]。
EXTRACT_JS = r"""() => {
  const clean = s => (s||'').trim().replace(/\s+/g,' ');
  // 注意: 「商品信息」表头所在的 .next-table 是**表头表**(table-header), 里面没有数据行;
  // 用 gridTh.closest('.next-table') 当作用域会拿到 0 行。数据行在文档级的 table.next-table-row 上,
  // 靠 !x.querySelector('thead') 排除表头/容器表即可。
  const rows = [...document.querySelectorAll('table.next-table-row')]
    .filter(x => !x.querySelector('thead') && clean(x.innerText));
  return rows.map(row => {
    const trs = [...row.querySelectorAll('tbody > tr')];
    const hdr = trs.find(t => t.classList.contains('next-table-group-header')) || trs[0];
    const body = trs.find(t => !t.classList.contains('next-table-group-header')) || trs[trs.length-1];
    const tds = body ? [...body.querySelectorAll(':scope > td')] : [];
    const col0 = tds[0];
    const titles = col0 ? [...col0.querySelectorAll('a[title]')].map(a => a.getAttribute('title')) : [];
    return {
      header: clean(hdr ? hdr.innerText : ''),
      cells: tds.map(td => clean(td.innerText)),
      title: titles[0] || null,
      sku: titles[1] || null,
      raw: clean(row.innerText),
    };
  });
}"""


def parse_row(r):
    """EXTRACT_JS 抽出的行 → build_refund_row 的输入 dict。"""
    header = r.get("header") or ""
    raw = r.get("raw") or ""
    cells = r.get("cells") or []
    c0 = cells[0] if len(cells) > 0 else ""
    c1 = cells[1] if len(cells) > 1 else ""
    c2 = cells[2] if len(cells) > 2 else ""
    c3 = cells[3] if len(cells) > 3 else ""
    text = header + " " + raw

    def grp(pat, s, flags=0):
        m = re.search(pat, s, flags)
        return m.group(1).strip() if m else None

    return {
        "refund_no": grp(r"退款编号[:：]?\s*(\d{6,})", text, re.S),
        "order_no": grp(r"订单号[:：]?\s*(\d{10,})", text, re.S),
        "after_sale_type": None,
        "status": grp(r"售后状态\s*[:：]?\s*(\S+)", c3),
        "refund_amount": grp(r"退款总额\s*[:：]?\s*[￥¥]?\s*([\d.]+)", c1),
        "order_amount": grp(r"买家实付\s*[:：]?\s*[￥¥]?\s*([\d.]+)", c1),
        "apply_time": grp(r"申请时间\s*[:：]?\s*(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d)", text),
        "finish_time": None,
        "reason": grp(r"原因\s*[:：]?\s*(.+?)\s*件数", c2),
        "product_title": r.get("title") or None,
        "sku_name": r.get("sku") or None,
        "item_id": grp(r"商品ID\s*[:：]?\s*(\d{6,})", c0),
        "buyer_nick": grp(r"申请时间\s*[:：]?\s*20\d\d-\d\d-\d\d \d\d:\d\d:\d\d\s+(\S+)", header),
        "raw": raw,
    }


def read_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            pg = json.load(f)
    else:
        pg = {}
    pg.setdefault("done", [])
    return pg


async def safe_count(loc, timeout=8):
    """Locator.count() 带超时: CDP 卡死时不会无限阻塞。"""
    try:
        return await asyncio.wait_for(loc.count(), timeout=timeout)
    except Exception:
        return 0


def save_progress(pg):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(pg, f, ensure_ascii=False, indent=2)


async def close_leaked_tabs(ctx, my_url_sub="trade-platform/refund-list"):
    """关闭本次运行之外的泄漏标签: 其它 refund-list 页 + xdomain-storage 跨域存储帧。

    退款页 SPA 极重, 残留 2-3 个就渲染进程 OOM(Page.reload: Page crashed)。
    xdomain frame.html 是 success/加载时弹出的子窗口, page.close() 管不到(见 sourcing AGENTS 标签泄漏治本)。
    """
    closed = 0
    for p in list(ctx.pages):
        try:
            u = p.url or ""
            if u.startswith(("chrome://", "devtools://")):
                continue
            if "xdomain-storage" in u or (
                    my_url_sub in u and p is not getattr(close_leaked_tabs, "_mine", None)):
                await p.close()
                closed += 1
        except Exception:
            pass
    if closed:
        log(f"  清理泄漏标签 {closed} 个")
    return closed


async def dismiss_guide(page):
    """driver.js 新手引导浮层会拦截一切点击 → 移除(纯客户端, 无副作用)。"""
    try:
        await asyncio.wait_for(page.evaluate(r"""() => {
          document.querySelectorAll('.driver-overlay,.driver-popover,.driver-popover-wrapper')
            .forEach(e => e.remove());
          document.body.classList.remove('driver-active','driver-fade');
        }"""), timeout=15)
    except Exception as e:
        log(f"  引导浮层清理失败(忽略): {type(e).__name__}: {str(e)[:100]}")


async def _any_visible(loc, timeout=4):
    """locator 中是否有任一可见元素(下拉未卸载时 .first 可能是隐藏项)。"""
    n = await safe_count(loc)
    for i in range(n):
        try:
            if await asyncio.wait_for(loc.nth(i).is_visible(), timeout=timeout):
                return True
        except Exception:
            pass
    return False


async def ensure_history_scope(page):
    """退款时间 scope 切到「历史退款」(只有它按日期区间查), 并回读确认。

    只在开跑时调一次: 点售后类型 tab / 设日期 / 搜索都不会把 scope 切回「最近申请」。
    返回 True=已确认 scope 为「历史退款」; False=无法确认(调用方须按未确认处理, 不得标记完成)。
    回读而非"点完就信": scope 错时日期输入框仍在, 日期回填会照常通过, 错窗口会被静默标 ok。
    """
    try:
        online = page.get_by_text("最近申请", exact=True).first
        if await safe_count(online) and await asyncio.wait_for(online.is_visible(), timeout=6):
            await asyncio.wait_for(online.click(timeout=6000), timeout=9000)
            await page.wait_for_timeout(1000)
            opt = page.get_by_text("历史退款", exact=True).first
            await asyncio.wait_for(opt.click(timeout=6000), timeout=9000)
            await page.wait_for_timeout(2500)
        if not await _any_visible(page.get_by_text("历史退款", exact=True)):
            log("  退款时间 scope 未确认: 未见「历史退款」(疑仍在「最近申请」)")
            return False
        log("退款时间 scope = 历史退款 (已确认)")
        return True
    except Exception as e:
        log(f"  切历史退款失败/未确认: {type(e).__name__}: {str(e)[:120]}")
        return False


async def click_type_tab(page, label):
    """按精确文本点售后类型 tab (li.next-tabs-tab)。

    「历史退款」视图下 tab 文本可能与 TYPES 略有出入(实测 退运费 → 退运费(已收货)),
    故先精确匹配, 再退化为前缀匹配。
    """
    loc = page.locator("li.next-tabs-tab")
    n = await safe_count(loc)
    texts = []
    for i in range(n):
        try:
            texts.append((await asyncio.wait_for(loc.nth(i).inner_text(), timeout=4000)).strip())
        except Exception:
            texts.append("")
    if not [t for t in texts if t]:
        raise StructuralError("页面无任何售后类型 tab (未登录/SPA 未渲染/结构变更)")
    idx = None
    for want in (label, f"{label}(已收货)"):
        if want in texts:
            idx = texts.index(want)
            break
    if idx is None:
        for i, txt in enumerate(texts):
            if txt.startswith(label):
                idx = i
                break
    if idx is None:
        log(f"  未找到售后类型 tab: {label!r} (现有: {texts})")
        return False
    await asyncio.wait_for(loc.nth(idx).click(timeout=6000), timeout=9000)
    await page.wait_for_timeout(2500)
    return True


async def set_date_range(page, start, end):
    """点起始日期 → 面板里填起止日 → Enter。用稳定的面板子类选择器。"""
    for _ in range(3):
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(150)
    await asyncio.wait_for(
        page.locator('input[placeholder="起始日期"]').first.click(timeout=6000), timeout=9000)
    await page.wait_for_timeout(1200)
    s = page.locator(".next-range-picker-panel-input-start-date input").first
    e = page.locator(".next-range-picker-panel-input-end-date input").first
    if not await safe_count(s) or not await safe_count(e):
        log("  日期面板未出现, 跳过设日期")
        await page.keyboard.press("Escape")
        return False
    await asyncio.wait_for(s.fill(start, timeout=5000), timeout=8000)
    await page.wait_for_timeout(300)
    await asyncio.wait_for(e.fill(end, timeout=5000), timeout=8000)
    await page.wait_for_timeout(300)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(1000)
    got_s = await asyncio.wait_for(
        page.locator('input[placeholder="起始日期"]').first.input_value(), timeout=6000)
    got_e = await asyncio.wait_for(
        page.locator('input[placeholder="结束日期"]').first.input_value(), timeout=6000)
    if not (got_s.startswith(start) and got_e.startswith(end)):
        log(f"  日期未回填 s={got_s!r}/{start} e={got_e!r}/{end}")
        await page.keyboard.press("Escape")
        return False
    return True


async def reload_page(page):
    """整页重载, 释放重 SPA 的内存(长跑防渲染进程 crash)。"""
    await asyncio.wait_for(page.reload(wait_until="domcontentloaded", timeout=60000), timeout=90)
    await page.wait_for_timeout(9000)
    await dismiss_guide(page)
    await ensure_history_scope(page)


async def click_search(page):
    btn = page.locator("button", has_text="搜索售后单").first
    try:
        await btn.scroll_into_view_if_needed(timeout=4000)
    except Exception:
        pass
    await asyncio.wait_for(btn.click(timeout=8000), timeout=11000)
    await page.wait_for_timeout(7000)


async def next_page(page):
    loc = page.locator('button:has-text("下一页")').first
    if not await safe_count(loc):
        return False
    try:
        disabled = await asyncio.wait_for(loc.evaluate(
            "e => { const li=e.closest('li'); return !!(li && li.className.includes('disabled')) "
            "|| !!e.disabled || (e.className||'').includes('disabled'); }"), timeout=6000)
    except Exception as e:
        # 判据读不到 = 状态不明 → 当作已到末页 break, 绝不盲目点(否则可能死循环到看门狗)
        log(f"  下一页禁用态读取失败, 视为末页: {type(e).__name__}: {str(e)[:80]}")
        return False
    if disabled:
        return False
    await asyncio.wait_for(loc.click(timeout=6000), timeout=9000)
    await page.wait_for_timeout(4000)
    return True


async def run(args):
    months = args.window_months
    if months and months > 0:
        windows = month_windows(args.dfrom, args.dto, months)
    else:
        windows = quarter_windows(args.dfrom, args.dto)
    b, ctx = await asyncio.wait_for(
        connect_cdp(PORT, keep_urls=["myseller.taobao.com", "taobao.com", "ufuwu.1688.com"], log=log),
        timeout=90)
    conn = None if args.dry_run else connect_db()
    pg = read_progress()
    last_total = {"total": None}
    try:
        shop_id = 0
        if conn:
            with conn.cursor() as c:
                shop_id = default_shop_id(c, PLATFORM_TAOBAO) or 0
        # 先清掉上次运行泄漏的重 SPA 标签(每次残留 1-2 个 refund-list/xdomain 就会 OOM crash)
        await close_leaked_tabs(ctx)
        page = await ctx.new_page()
        close_leaked_tabs._mine = page

        async def on_resp(r):
            if "disputelistv2" in r.url:
                try:
                    j = json.loads(await r.text())
                    last_total["total"] = (j.get("data", {}).get("resultData", {})
                                           .get("disputeGridInfoVO", {}).get("paginationVO", {})
                                           .get("total"))
                except Exception:
                    pass
        page.on("response", lambda r: asyncio.ensure_future(on_resp(r)))
        try:
            await asyncio.wait_for(page.goto(URL, wait_until="domcontentloaded", timeout=60000), timeout=90)
            await page.wait_for_timeout(12000)
            await dismiss_guide(page)
            await ensure_history_scope(page)
            total_written = 0
            limit_left = args.limit if args.limit else None
            processed = 0
            succeeded = 0
            failed = 0
            unconfirmed = 0
            structural_fail = False

            async def do_window(a_type, start, end):
                """处理单个 类型+窗口 → (状态, 写入行数)。

                状态:
                  "ok"          = 日期区间已确认 + 翻完 → 可标记 done(含真 0 行)
                  "limited"     = 命中 --limit 截断 → **不**标记 done(冒烟测试)
                  "unconfirmed" = 日期区间或退款时间 scope 未确认 → **不**标记 done(下次重试)
                结构异常(tab 全无)抛 StructuralError 由外层识别。
                """
                nonlocal limit_left
                key = f"{a_type}|{start}~{end}"
                # 每窗口整页重载: 退款页 SPA 极重, 复用同一页面 2-3 个窗口就 Target crashed;
                # reload 顺带做 dismiss_guide + ensure_history_scope(回读确认)
                await reload_page(page)
                if not await ensure_history_scope(page):
                    log(f"  警告: {key} 退款时间 scope 未确认(非历史退款), "
                        f"跳过且**不标记完成**(下次重试)")
                    return ("unconfirmed", 0)
                if not await click_type_tab(page, a_type):
                    if not await ensure_history_scope(page):
                        log(f"  警告: {key} scope 复核未通过, 跳过且**不标记完成**")
                        return ("unconfirmed", 0)
                    if not await click_type_tab(page, a_type):
                        raise RuntimeError(f"未找到类型 tab {a_type}")
                if not await set_date_range(page, start, end):
                    log(f"  警告: {key} 日期未确认, 跳过且**不标记完成**(下次重试)")
                    return ("unconfirmed", 0)
                await click_search(page)
                log(f"{key}: 页面合计 {last_total['total']} 条")
                page_no, written, limited = 1, 0, False
                while page_no <= args.max_pages:
                    # 单窗口 >4 页必 Target crashed(SPA 每页 20 张重卡片累积) →
                    # 每 4 页整页重载并重建现场(切tab→设日期→搜索→连点下一页跳回本页)
                    if page_no > 1 and (page_no - 1) % 2 == 0:
                        log(f"  {key} 第{page_no}页前主动重载防崩…")
                        await reload_page(page)
                        if not (await ensure_history_scope(page)
                                and await click_type_tab(page, a_type)
                                and await set_date_range(page, start, end)):
                            raise RuntimeError(f"{key} 第{page_no}页重载后现场重建失败")
                        await click_search(page)
                        for _ in range(page_no - 1):
                            if not await next_page(page):
                                break
                            await page.wait_for_timeout(500)
                    rows = await asyncio.wait_for(page.evaluate(EXTRACT_JS), timeout=30)
                    if not rows:
                        break
                    for r in rows:
                        row = build_refund_row(parse_row(r), shop_id)
                        if row is None:
                            continue
                        row["after_sale_type"] = a_type
                        if args.dry_run:
                            log(f"  [dry] {row['refund_no']} {row['after_sale_type']} "
                                f"¥{row['refund_amount']} {row['status']} {row['apply_time']} "
                                f"| {row['product_title']} | {row['sku_name']} | id={row['item_id']}")
                            written += 1
                        else:
                            written += upsert_refund_order(conn, row)
                        if limit_left is not None:
                            limit_left -= 1
                            if limit_left <= 0:
                                limited = True
                                break
                    if not args.dry_run and written:
                        conn.commit()
                    log(f"  {key} 第{page_no}页: {len(rows)} 行 (累计 {written})")
                    if limited:
                        break
                    if not await next_page(page):
                        break
                    page_no += 1
                return ("limited", written) if limited else ("ok", written)

            stop = False
            for a_type in (args.types or TYPES):
                for start, end in windows:
                    key = f"{a_type}|{start}~{end}"
                    if (not args.force and not args.dry_run) and key in pg["done"]:
                        log(f"跳过已完成 {key}")
                        continue
                    if processed and processed % 5 == 0:
                        # 重 SPA 长跑后渲染进程易 crash → 定期整页重载释放内存
                        log("  定期重载页面释放内存…")
                        try:
                            await reload_page(page)
                        except Exception as e:
                            log(f"  重载失败(继续): {type(e).__name__}: {str(e)[:120]}")
                    try:
                        status, written = await asyncio.wait_for(
                            do_window(a_type, start, end), timeout=args.window_timeout)
                    except StructuralError as e:
                        structural_fail = True
                        failed += 1
                        log(f"  窗口 {key} 结构异常: {e}")
                        stop = True
                        break
                    except Exception as e:
                        # 渲染进程崩了 → 继续只会连锁全崩, 抛出交给 main() 重启 Chrome 再续跑
                        if "crashed" in str(e).lower() or "context management" in str(e).lower():
                            raise
                        failed += 1
                        log(f"  窗口 {key} 失败(跳过, 下次重试): {type(e).__name__}: {str(e)[:140]}")
                        continue
                    if status == "unconfirmed":
                        unconfirmed += 1
                        continue
                    log(f"{key}: 写入 {written} ({status})")
                    total_written += written
                    processed += 1
                    succeeded += 1
                    if not args.dry_run and status == "ok":
                        if key not in pg["done"]:
                            pg["done"].append(key)
                            save_progress(pg)
                    if status == "limited":
                        stop = True
                        break
                if stop:
                    break
            if not args.dry_run:
                n = refresh_derived_import_orders(conn, shop_id, PLATFORM_TAOBAO,
                                                  args.dfrom, args.dto)
                conn.commit()
                log(f"派生 refund_import_order: {n} 行 (code={DERIVED_CODE})")
                ensure_auto_report(conn, shop_id, PLATFORM_TAOBAO, args.dfrom, args.dto)
                conn.commit()
            attempted = succeeded + failed + unconfirmed
            log(f"完成: 退款记录写入 {total_written}; 成功 {succeeded} / 失败 {failed} / "
                f"未确认 {unconfirmed} / 结构异常 {structural_fail}")
            if structural_fail:
                log("结构异常 → 退出码 2")
                return 2
            if attempted and succeeded == 0:
                log("全部窗口失败 → 退出码 1")
                return 1
            return 0
        finally:
            await page.close()
            close_leaked_tabs._mine = None
            await close_leaked_tabs(ctx)
    finally:
        if conn:
            conn.close()
        try:
            await b.close()
        except Exception:
            pass


async def restart_chrome_with_login():
    """杀掉崩溃的 9222 实例并以窗口模式重启, 再用登录备份注回 cookie(不需人工扫码)。

    崩过的渲染进程会连锁 `Page.reload: Page crashed`, 只有重启实例才能恢复。
    """
    log("  重启 9222 (实例崩溃后必须重启才能恢复)…")
    import subprocess
    subprocess.run(["pkill", "-f", "remote-debugging-port=9222"], check=False)
    await asyncio.sleep(4)
    subprocess.Popen([
        "arch", "-arm64", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.join(BASE, 'chrome-profile')}",
        "--no-first-run", "--disable-extensions",
        "--disable-features=TranslateUI,site-per-process", "--disable-background-timers",
        "--disable-backgrounding-occluded-windows", "--disable-background-networking",
        "--renderer-process-limit=6", "--js-flags=--max-old-space-size=512",
        "--window-position=-32000,-32000", "--window-size=1400,900",
        "https://myseller.taobao.com/home.htm/trade-platform/refund-list",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    up = False
    for _ in range(20):
        await asyncio.sleep(1.5)
        try:
            import urllib.request
            with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3) as r:
                if r.status == 200:
                    up = True
                    break
        except Exception:
            continue
    if not up:
        raise RuntimeError("重启后 9222 未就绪")
    await asyncio.sleep(3)
    # 复用 restore_login_cookies: 掉登录时自动注回(不覆盖有效会话)
    from restore_login_cookies import main as restore_main
    rc = await restore_main()
    log(f"  重启完成, 登录恢复 rc={rc}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default=RETENTION_START)
    ap.add_argument("--to", dest="dto", default=date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=80)
    ap.add_argument("--types", nargs="*", default=None)
    ap.add_argument("--window-months", type=int, default=6,
                    help="日期窗粒度(月); 6=半年窗(默认, 比季度窗少一半固定开销), 0=季度窗")
    ap.add_argument("--force", action="store_true", help="忽略进度重跑")
    ap.add_argument("--window-timeout", type=int, default=180, help="单窗口看门狗秒数")
    args = ap.parse_args()
    attempts = 0
    while True:
        try:
            sys.exit(asyncio.run(run(args)))
        except SystemExit:
            raise
        except Exception as e:
            attempts += 1
            log(f"运行异常(第{attempts}次), 将重连续跑: {type(e).__name__}: {str(e)[:160]}")
            # 崩过的 Chrome 实例会连锁 Page.reload: Page crashed → 必须重启实例才能恢复
            if "crashed" in str(e).lower() or "context management" in str(e).lower():
                try:
                    asyncio.run(restart_chrome_with_login())
                except Exception as re_:
                    log(f"重启 9222 失败(继续用原实例): {type(re_).__name__}: {str(re_)[:120]}")
            if attempts >= 6:
                log("重试次数用尽, 退出(进度文件保留, 可再跑)")
                sys.exit(1)
            time.sleep(15)


if __name__ == "__main__":
    main()
