#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 1688 ISV 分销工作台「全部」代发单 → order_source_relation。

只读: 只点「全部」tab /「更多」展开 / 日期区间 /「查 询」/ 翻页 / 关密文提示;
绝不点 采购/打单/发货/关闭/忽略/编辑。

关于覆盖(2026-10-12 实测, 见 task-3-report.md 覆盖尝试):
  ISV「全部」声明 共203条, 但整段只渲染 167 行(到 2026-02-11 停, 第 11 页为空)。
  按日期分窗后, 较新窗口能完整渲染, 但 2026-02 之前的订单是「计数但不渲染」
  (如窗口 2026-02-11~02-28 声明 共11条 却只渲染 6 行, 无分页/无虚拟滚动可救)。
  因此给定 --from/--to 只会设置下单时间区间, **不会**增加可获得的行 —— 这是平台侧限制。
  故本采集器单段翻页即可; --from/--to 可选, best-effort 设置区间。

断点续跑: 单段幂等 upsert, 无需进度文件。
跑法:
  automation/venv/bin/python tb-auto/collect_1688_agency_order.py --dry-run
  automation/venv/bin/python tb-auto/collect_1688_agency_order.py
  automation/venv/bin/python tb-auto/collect_1688_agency_order.py --from 2024-10-01 --to 2026-10-12
"""
import argparse
import asyncio
import os
import sys
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import (build_source_relation_row, connect_db, log, parse_isv_row,  # noqa: E402
                        upsert_source_relation)

PORT = 9222
URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"

EXTRACT_JS = r"""() => {
  const trs=[...document.querySelectorAll('.ant-table-row')].filter(t=>(t.innerText||'').trim());
  return trs.map(tr=>{
    const a=tr.querySelector('a[title="店铺订单号"]');
    const ot=(a?a.innerText:'').trim();
    const href=a?a.getAttribute('href')||'':'';
    const m=href.match(/biz_order_id=(\d+)/);
    // 行内有两个 span.order-id: 第一个是**淘宝**商品ID(见 platform_product.code),
    // 第二个(与商品标题的 detail.1688.com/offer/<id>.html 一致)才是 1688 货源商品ID。
    const offer=tr.querySelector('a[href*="detail.1688.com/offer/"]');
    const om=offer?(offer.getAttribute('href')||'').match(/offer\/(\d+)/):null;
    const ids=[...tr.querySelectorAll('span.order-id')];
    const spid=om?om[1]:(ids.length>1?(ids[ids.length-1].innerText||'').replace(/\D/g,''):'');
    return {
      shop_order_no: (m?m[1]:ot)||'',
      source_product_id: spid,
      raw:(tr.innerText||'').replace(/\n+/g,' / ')
    };
  });
}"""

# 注意: 必须用**精确**「查询」(去空白后 === '查询')。页面还有个「查询项设置」按钮,
# 正则 /查\s*询/ 会先命中它(点开设置弹窗且不触发查询), 这是区间不生效的根因。
QUERY_JS = r"""() => {
  const b=[...document.querySelectorAll('button')]
    .find(b=>(b.innerText||'').replace(/\s/g,'')==='查询' && b.offsetParent!==null);
  if(b){ b.click(); return true; } return false;
}"""


async def open_order_list(p):
    await p.goto(URL, wait_until="domcontentloaded", timeout=60000)
    await p.wait_for_timeout(12000)
    frame = next((f for f in p.frames if "isv-container" in f.url), None)
    if frame is None:
        raise RuntimeError("找不到 isv-container iframe(登录态掉了?)")
    await frame.evaluate("() => { location.hash = '#/order/list'; }")
    await p.wait_for_timeout(7000)
    return next((f for f in p.frames if "isv-container" in f.url), frame)


async def close_secret_modal(frame):
    """只点**可见弹窗容器内**的「确 定」(密文提示是 ant-modal)。

    不再遍历点全页每个精确「确定」按钮——页面上其它表单/下拉的确定也会被误点。
    弹窗定位失败时宁可不点, 交给后续步骤自然报错。
    """
    clicked = await frame.evaluate(r"""() => {
      const modals=[...document.querySelectorAll('.ant-modal, .ant-modal-wrap, .ant-modal-confirm')]
        .filter(m=>m.getClientRects().length>0);
      for(const m of modals){
        const b=[...m.querySelectorAll('button')]
          .find(b=>/^确\s*定$/.test((b.innerText||'').trim()));
        if(b){ b.click(); return true; }
      }
      return false;
    }""")
    await frame.wait_for_timeout(1200)
    return clicked


async def pick_all_tab(frame):
    await frame.evaluate("""() => { const t=[...document.querySelectorAll('*')]
      .find(e=>/^全部\\s*\\(\\d+\\)$/.test((e.innerText||'').trim())&&e.children.length<=1); if(t)t.click(); }""")
    await frame.wait_for_timeout(2500)


async def query(frame):
    ok = await frame.evaluate(QUERY_JS)
    await frame.wait_for_timeout(7000)
    return ok


async def next_page(frame):
    return await frame.evaluate("""() => { const b=document.querySelector('.ant-pagination-next');
      if(!b || b.classList.contains('ant-pagination-disabled')) return false; b.click(); return true; }""")


async def date_input_width(frame):
    return await frame.evaluate(
        r"""() => { const i=[...document.querySelectorAll('input')].find(x=>(x.placeholder||'').includes('开始时间'));
            return i?Math.round(i.getBoundingClientRect().width):0; }""")


async def ensure_filters_expanded(frame):
    """「下单时间」表单项默认 display:none(在「更多/展开高级搜索选项」折叠区), 需展开后才能设置。"""
    if await date_input_width(frame) > 0:
        return True
    for _ in range(3):
        await frame.evaluate("""() => { const b=document.querySelector('button[aria-label="展开高级搜索选项"]');
            if(b) b.click(); }""")
        await frame.wait_for_timeout(1500)
        if await date_input_width(frame) > 0:
            return True
    return False


async def set_date_range(p, frame, start_dt, end_dt):
    """设置「下单时间」起止 (真实键盘输入; needConfirm 面板需点 footer「确 定」提交)。

    先清空 picker(否则第二次设置会把上次的结束值当成新起点)。返回 (ok, readback)。
    """
    await frame.evaluate(
        r"""() => { const c=document.querySelector('.combine-time-picker-wrapper .ant-picker-clear'); if(c) c.click(); }""")
    await p.wait_for_timeout(600)
    for ph, val in (("开始时间", start_dt), ("结束时间", end_dt)):
        loc = frame.locator(f'input[placeholder="{ph}"]').first
        await loc.click(click_count=3)
        await p.wait_for_timeout(300)
        await p.keyboard.type(val, delay=25)
        await p.wait_for_timeout(250)
        await p.keyboard.press("Enter")
        await p.wait_for_timeout(500)
    await frame.evaluate(r"""() => { const ds=[...document.querySelectorAll('.ant-picker-dropdown')]
        .filter(d=>!d.classList.contains('ant-picker-dropdown-hidden'));
        if(ds.length){ const b=ds[ds.length-1].querySelector('.ant-picker-ok button'); if(b) b.click(); } }""")
    await p.wait_for_timeout(600)
    rb = await frame.evaluate("() => [...document.querySelectorAll('.ant-picker-input input')].map(i=>i.value)")
    ok = len(rb) == 2 and rb[0][:10] == start_dt[:10] and rb[1][:10] == end_dt[:10]
    return ok, rb


async def run(args):
    b, ctx = await connect_cdp(PORT, keep_urls=["ufuwu.1688.com", "myseller.taobao.com", "taobao.com"], log=log)
    conn = None if args.dry_run else connect_db()
    stats = {"rows": 0, "written": 0, "no_source_no": 0}
    try:
        p = await ctx.new_page()
        try:
            frame = await open_order_list(p)
            await close_secret_modal(frame)
            await pick_all_tab(frame)

            # 可选: 设置下单时间区间(best-effort; 平台渲染上限使更宽区间并不能多采, 见文件头)
            if args.from_date:
                dto = args.to_date or date.today().isoformat()
                if await ensure_filters_expanded(frame):
                    ok, rb = await set_date_range(p, frame, f"{args.from_date} 00:00:00", f"{dto} 23:59:59")
                    log(f"下单时间区间 {args.from_date}~{dto}: {'已设置' if ok else '设置失败(用默认区间)'} {rb}")
                else:
                    log("下单时间区间: 无法展开「更多」(用默认区间)")
                await close_secret_modal(frame)

            if not await query(frame):
                raise RuntimeError("找不到「查 询」按钮")
            await close_secret_modal(frame)
            total = await frame.evaluate(
                r"""() => { const m=document.body.innerText.match(/共\s*([0-9,]+)\s*条/); return m?m[1]:'?'; }""")
            log(f"ISV 全部 共 {total} 条")
            for page in range(1, args.max_pages + 1):
                rows = await frame.evaluate(EXTRACT_JS)
                if not rows:
                    break
                for r in rows:
                    stats["rows"] += 1
                    isv = parse_isv_row(r["shop_order_no"], r["source_product_id"], None, r["raw"])
                    row = build_source_relation_row(isv)
                    if not row.get("source_order_no"):
                        stats["no_source_no"] += 1
                        if args.dry_run:
                            log(f"  [no采购单号] {r['shop_order_no']} :: {r['raw'][:120]}")
                        continue
                    if args.dry_run:
                        log(f"  [dry] {row['order_no']} <- 1688:{row['source_order_no']} "
                            f"¥{row['source_selling_price']} {row['order_status']} {row['order_time']}")
                    else:
                        stats["written"] += upsert_source_relation(conn, row)
                if not args.dry_run:
                    conn.commit()
                log(f"第{page}页: {len(rows)} 行")
                if not await next_page(frame):
                    break
                await p.wait_for_timeout(3500)
        finally:
            await p.close()
    finally:
        if conn:
            conn.close()
        await b.close()
    log(f"完成: 扫到 {stats['rows']} 行, 写入 {stats['written']}, 无采购单号 {stats['no_source_no']}")
    if stats["rows"] == 0:
        log("!! 警告: 未扫到任何行(页面结构/登录态异常?), 覆盖未确认 (退出码 3)")
        return 3  # 供 cron wrapper 报警: 0 行 ≠ 真实成功
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from", dest="from_date", default=None,
                    help="可选: 下单时间起 YYYY-MM-DD (best-effort, 不增加可获得行数)")
    ap.add_argument("--to", dest="to_date", default=None, help="可选: 下单时间止 YYYY-MM-DD, 默认今天")
    ap.add_argument("--max-pages", type=int, default=80)
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
