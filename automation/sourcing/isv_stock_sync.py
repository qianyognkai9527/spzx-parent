#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""isv_stock_sync.py — ISV 控制台「已关联货源」逐页批量库存同步 (2026-10-16)

用户口径的操作流：每页切 100 条/页 → 表头全选(本页) → 点「全量库存同步」→ 确定 → 下一页。
控制台没有跨页全选（表头勾选框只作用本页），所以全量=逐页循环。

用法:
  venv/bin/python isv_stock_sync.py                  # 全量（默认从第 1 页）
  venv/bin/python isv_stock_sync.py --start 5        # 断点续跑
  venv/bin/python isv_stock_sync.py --pages 2 --dry-run   # 预演（只选不点同步）
"""
import argparse
import asyncio
import json
import re
import sys
import time
import traceback

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from cdp_utils import connect_cdp, minimize_windows
from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli
import isv_sku_match as M

REPORT = '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/stock_sync_report.json'
PER_PAGE = 100

# 快捷筛选 chip 点击候选（按优先级两轮扫描）：
#   1) 『商品状态:销售中』（规格指定，2026-10-19 侦察：页面暂无此文本，防御性保留）
#   2) 『销售中(N)』带计数 chip —— 真身是 BUTTON.ten-ui-select-button-option（与好使的
#      『已关联货源(N)』同族）；2026-10-19 侦察实证：裸文本全等匹配只会点中表格行内
#      状态 tag（span.ant-tag-success），那就是筛选「假成功」的根因
#   3) 裸『销售中』兜底（末位，即上述陷阱元素）
CHIP_CLICK_JS = """() => {
  const els = [...document.querySelectorAll('span,div,button,a,li')];
  const pats = [/^商品状态:销售中$/, /^销售中[（(]/, /^销售中$/];
  for (const pat of pats) {
    for (let i = els.length - 1; i >= 0; i--) {
      const e = els[i];
      const t = (e.textContent||'').replace(/\\s+/g,'');
      if (pat.test(t) && e.children.length<=2) { e.click(); return t; }
    }
  }
  return null; }"""


def log(m):
    M.log(m)


def load_report():
    try:
        return json.load(open(REPORT, encoding='utf-8'))
    except Exception:
        return {"pages": {}}


async def body_text(fr):
    return await fr.inner_text("body")


async def risk_check(fr):
    body = await body_text(fr)
    if "RGV587" in body or "滑块" in body:
        return True
    return bool(await fr.locator("#nc_1_wrapper").count())


async def set_page_size(fr, size=PER_PAGE):
    sc = fr.locator(".ant-pagination-options-size-changer").first
    if not await sc.count():
        log("!! 没找到每页条数选择器")
        return False
    cur = (await sc.inner_text()).strip()
    if str(size) in cur:
        return True
    try:
        await fr.keyboard.press("Escape")
        await asyncio.sleep(1)
    except Exception:
        pass
    for attempt in (1, 2):
        await sc.click(timeout=6000)
        await asyncio.sleep(1.5)
        dd = fr.locator(".ant-select-dropdown:not(.ant-select-dropdown-hidden)")
        opt = dd.locator(f".ant-select-item-option[title*='{size}']").first
        if not await opt.count():
            opt = dd.locator(f"text=/{size}\\s*条/页/").first
        if not await opt.count():
            log(f"!! 下拉里没有 {size} 条/页 选项")
            return False
        try:
            await opt.click(timeout=8000, force=(attempt == 2))
        except Exception as e:
            log(f"!! 点 {size} 条/页 失败(尝试{attempt}): {str(e)[:60]}")
            if attempt == 2:
                return False
        await asyncio.sleep(4)
        cur = (await sc.inner_text()).strip()
        if str(size) in cur:
            return True
        log(f"回读未变({cur}），重试")
    return False


async def active_page(fr):
    try:
        t = await fr.locator(".ant-pagination-item-active").first.inner_text(timeout=4000)
        return int(t.strip())
    except Exception:
        return None


async def total_pages(fr):
    try:
        t = await fr.locator(".ant-pagination-item-ellipsis, .ant-pagination-jump-prev, .ant-pagination-jump-next").first.count()
        items = await fr.locator(".ant-pagination-item").all_inner_texts()
        if items:
            return max(int(x) for x in items if x.strip().isdigit())
    except Exception:
        pass
    return None


async def select_all_page(fr, force_recheck=False):
    cb = fr.locator(".ant-table-thead .ant-checkbox-input").first
    if force_recheck:
        try:
            await cb.uncheck(timeout=5000)
        except Exception:
            pass
    for attempt in range(3):
        try:
            await cb.check(timeout=10000)
            break
        except Exception as e:
            log(f"   全选点击重试{attempt + 1}: {str(e)[:50]}")
            await wait_no_modal(fr)
            await asyncio.sleep(2)
            if attempt == 2:
                raise
    await asyncio.sleep(1.2)
    sel = await fr.evaluate("""() => {
      const out=[];
      for (const e of document.querySelectorAll('*')) {
        const t=(e.textContent||'').trim();
        if(t && t.length<30 && /已选/.test(t) && e.children.length<=2) out.push(t);
      }
      return Array.from(new Set(out)).slice(0,5);
    }""")
    return sel


def page_select_ok(sel, n_rows):
    """全选校验（纯函数）：已选计数必须=本页行数（容忍『已选N/共N』式文案）。"""
    want = f"已选{n_rows}/{n_rows}"
    return any(want in s or f"已选{n_rows}/" in s for s in (sel or []))


async def click_sync(fr):
    for label in ("全量库存同步", "批量同步库存"):
        info = await fr.evaluate("""(needle) => {
          for (const e of document.querySelectorAll('button, .ant-btn, a, span')) {
            const t=(e.innerText||'').trim();
            if(t===needle) {
              const b = e.closest('button') || e;
              return {found: true, disabled: b.disabled===true};
            }
          }
          return {found: false};
        }""", label)
        if info.get("found") and not info.get("disabled"):
            await fr.get_by_text(label, exact=True).first.click(timeout=6000)
            return label
    return None


async def confirm_modal(fr):
    await asyncio.sleep(2)
    dlg = await fr.evaluate("""() => {
      const d=document.querySelector('.ant-modal:not([style*="display: none"]) .ant-modal-body');
      return d ? (d.innerText||'').slice(0,400) : null;
    }""")
    log(f"   弹窗: {(dlg or '无').replace(chr(10), ' / ')[:120]}")
    if dlg and "同步" in dlg:
        btn = fr.locator(".ant-modal:not([style*='display: none']) button", has_text="确").first
        if await btn.count():
            await btn.click(timeout=6000)
            await asyncio.sleep(2)
            return True
    return False


async def wait_no_modal(fr, timeout_s=10):
    """同步确认后弹窗可能残留数秒（提交 100 条服务端排队），等它消失再翻页。"""
    for _ in range(timeout_s * 2):
        vis = await fr.evaluate(
            "() => !!document.querySelector('.ant-modal:not([style*=\"display: none\"])')")
        if not vis:
            return True
        await asyncio.sleep(0.5)
    await fr.evaluate("""() => {
      const c=document.querySelector('.ant-modal:not([style*="display: none"]) .ant-modal-close');
      if(c) c.click();
    }""")
    await asyncio.sleep(1.5)
    return False


async def goto_page(fr, target):
    await wait_no_modal(fr)
    for _ in range(target + 2):
        cur = await active_page(fr)
        if cur == target:
            return True
        if cur is not None and cur > target:
            return False
        nxt = fr.locator(".ant-pagination-next").first
        cls = await nxt.get_attribute("class") or ""
        if "ant-pagination-disabled" in cls:
            return False
        try:
            await nxt.click(timeout=6000)
        except Exception:
            await wait_no_modal(fr)
            await fr.evaluate("""() => {
              const n=document.querySelector('.ant-pagination-next');
              if(n) n.click();
            }""")
        await asyncio.sleep(2.5)
    return False


async def run(args):
    rep = {"pages": {}}  # 每轮从空开始：run_stock_sync.sh 汇总的 rows 必须只含本轮
    b, ctx = await connect_cdp(9222, keep_urls=["fuwu_work_isv_container", "isv-container",
                                                "taobao.com", "1688.com"], log=log, minimize=True)
    page = None
    try:
        page = await open_page(ctx, quiet=True)
        await minimize_windows(ctx, log=lambda m: None)
        fr = await get_frame(page)
        if not fr:
            log("!! 没找到 isv-container iframe（登录态掉了？）")
            return 2
        if not await fr.locator(".ant-table-row").first.count():
            await nav_to_guanli(fr)
        # 已关联货源
        await fr.evaluate("""() => {
          const els=[...document.querySelectorAll('*')].filter(e=>{
            const t=(e.textContent||'').trim();
            return t.startsWith('已关联货源') && t.length<20 && e.children.length<=2;});
          if(els.length) els[els.length-1].click();}""")
        await asyncio.sleep(4)
        body = await body_text(fr)
        m = re.search(r'已关联货源[（(]?([\d,]+)', body)
        total = int(m.group(1).replace(',', '')) if m else 0
        log(f"已关联货源 {total} 个")

        if args.scope == "onsale":
            clicked = await fr.evaluate(CHIP_CLICK_JS)
            await asyncio.sleep(4)
            body = await body_text(fr)
            m = re.search(r'销售中[（(]([\d,]+)', body)
            total = int(m.group(1).replace(',', '')) if m else 0
            log(f"在售口径: 销售中 {total} 个 (筛选点击: {clicked})")
            if not total:
                log("!! 销售中计数为 0, 放弃本轮")
                return 4

        if not await set_page_size(fr):
            log("切 100条/页 未生效，等 5s 重试一次")
            await asyncio.sleep(5)
            if not await set_page_size(fr):
                return 3
        n_rows = await fr.locator(".ant-table-row").count()
        if n_rows < PER_PAGE:
            log(f"!! 每页仍只有 {n_rows} 行，100条/页 未生效，中止")
            return 3
        if args.scope == "onsale":
            # 校验门必须在 100条/页 基准上比（新会话默认 20条/页时，889 条=45 页 > 9 页必误报），
            # 故置于 set_page_size 之后；严格度不变：actual > expected 即 rc=9
            expected_pages = -(-total // PER_PAGE)
            actual_pages = await total_pages(fr)
            if actual_pages is not None and actual_pages > expected_pages:
                log(f"!! 筛选疑似未生效（计数 {total} 但分页 {actual_pages} 页 > 预期 {expected_pages} 页），重试前缀 chip")
                clicked = await fr.evaluate(CHIP_CLICK_JS)
                log(f"   chip 重试点击: {clicked}")
                await asyncio.sleep(4)
                if not await set_page_size(fr):
                    log("   重试后切 100条/页 未生效")
                body = await body_text(fr)
                m = re.search(r'销售中[（(]([\d,]+)', body)
                total = int(m.group(1).replace(',', '')) if m else 0
                actual_pages = await total_pages(fr)
                if actual_pages is not None and actual_pages > expected_pages:
                    log(f"!! 在售筛选未生效（计数 {total} 但分页 {actual_pages} 页=全量口径），本轮放弃")
                    return 9
            if actual_pages is not None:
                log(f"在售筛选校验通过: 分页 {actual_pages} 页 ≤ 预期 {expected_pages} 页 (计数 {total})")
            else:
                log("在售筛选校验: 分页不可读, 跳过校验")
        npages = await total_pages(fr) or -(-total // PER_PAGE)
        npages_eff = min(npages, args.start + args.pages - 1) if args.pages else npages
        log(f"每页 {PER_PAGE} → 本页 {n_rows} 行, 共 {npages} 页")

        for pg in range(args.start, npages_eff + 1):
            cur = await active_page(fr)
            if cur is not None and cur != pg:
                if not await goto_page(fr, pg):
                    log(f"!! 翻到第 {pg} 页失败，停止")
                    return 4
            if await risk_check(fr):
                log("!! 出现滑块/风控，停止本轮")
                return 5
            ok = False
            for attempt in range(3):
                n_rows = await fr.locator(".ant-table-row").count()
                sel = await select_all_page(fr, force_recheck=(attempt > 0))
                if page_select_ok(sel, n_rows):
                    ok = True
                    break
                log(f"第 {pg} 页选中异常(尝试{attempt + 1}/3): {sel}, 清弹窗后重选")
                await wait_no_modal(fr, 15)
                await asyncio.sleep(3 * (attempt + 1))
            if not ok:
                log(f"第 {pg} 页重选 3 次仍异常, 放弃本轮")
                return 6
            want = f"已选{n_rows}/{n_rows}"
            if args.dry_run:
                log(f"[{pg}/{npages}] DRY {want}")
            else:
                label = await click_sync(fr)
                if not label:
                    log(f"!! 第 {pg} 页找不到同步按钮，停止")
                    return 7
                if not await confirm_modal(fr):
                    log(f"!! 第 {pg} 页确认弹窗异常，停止")
                    return 8
                await minimize_windows(ctx, log=lambda m: None)
                log(f"[{pg}/{npages}] {want} → {label} 已提交")
            rep["pages"][str(pg)] = {"rows": n_rows, "ts": time.strftime("%F %T"),
                                     "dry": bool(args.dry_run)}
            json.dump(rep, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            if pg < npages_eff:
                if not await goto_page(fr, pg + 1):
                    log(f"!! 翻到第 {pg + 1} 页失败，停止（已同步到第 {pg} 页）")
                    return 4
        log(f"完成: {npages_eff} 页 × {PER_PAGE} 条{' (DRY)' if args.dry_run else ''}")
        return 0
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--pages", type=int, default=0, help="最多跑几页(调试用)")
    ap.add_argument("--scope", choices=("onsale", "all"), default="onsale",
                    help="onsale=只处理销售中(默认, 9页, spec 2026-10-19); all=全部已关联货源(旧行为)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        rc = asyncio.get_event_loop().run_until_complete(run(args))
    except Exception:
        traceback.print_exc()
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
