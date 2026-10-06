#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISV 铺货失败批量重发布 (2026-09-27):
对每条铺货失败记录: 直接打开 from1688 草稿编辑器 → 店铺分类(八类目,长裤→休闲裤别名)
→ 运费模板 → catProp 必填(版型等) → 放入仓库 → 合规必填 → 提交.
尺码表不填(用户确认非阻塞). 不改价不动图.
进度: isv_republish_progress.json {fixed: [], failed: {}}."""
import asyncio
import json
import os
import random
import sys
import time

from cdp_utils import connect_cdp
from assign_shop_category import (
    wait_edit_ready, scroll_edit_page, handle_recommend_dialog,
    ensure_extract_way, set_shop_category, click_submit, cleanup_leaked_tabs, log,
)
from assign_shop_category_v2 import ensure_guard_tab, run_compliance_fill
from build_shop_cat_plan import classify
from compliance_filler import clear_overlays, ensure_no_overlay

BASE = '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing'
PROG_FILE = f'{BASE}/isv_republish_progress.json'
CDP_PORT = 9222
TEMPLATE = '一件包邮--浙江杭州'
EDITOR_URL = 'https://item.upload.taobao.com/from1688/render.htm?sourceId={oid}&newPublish=true&from1688PredictCacheId={oid}&offerId={oid}'

STATE_JS = """() => {
  const st = document.querySelector('#sell-field-startTime');
  let r = null;
  if (st) {
    for (const w of st.querySelectorAll('label')) {
      const i = w.querySelector('input');
      const t = (w.textContent||'').trim();
      if (i && i.checked && t) r = t.slice(0, 10);
    }
  }
  const tpl = document.querySelector('#sell-field-tbExtractWay span.next-select');
  return {startTime: r, template: tpl ? (tpl.innerText||'').trim().slice(0, 25) : null};
}"""

OPTIONS_JS = """() => {
  const ws = [...document.querySelectorAll('.next-overlay-wrapper.opened')];
  return ws.length ? [...ws[ws.length - 1].querySelectorAll('.options-item, .next-menu-item')]
      .map(e => e.getAttribute('title') || (e.innerText||'').trim()).filter(Boolean).slice(0, 25) : null;
}"""

BANXING_ALIAS = (('宽松', ('阔腿', '宽松', '慵懒')), ('直筒', ('直筒',)), ('修身', ('修身', '显瘦')),
                 ('紧身', ('紧身',)), ('锥形', ('微喇', '喇叭', '锥形')), ('加长', ('加长',)))


def load_prog():
    if os.path.exists(PROG_FILE):
        return json.load(open(PROG_FILE))
    return {'fixed': [], 'failed': {}}


def save_prog(prog):
    json.dump(prog, open(PROG_FILE, 'w'), ensure_ascii=False, indent=1)


async def ensure_template(page):
    st = await page.evaluate(STATE_JS)
    if st is None:
        return False, 'NO_ZONE'
    if st['template'] == TEMPLATE:
        return True, '模板已是目标值'
    if not await page.locator('#sell-field-tbExtractWay label:has-text("使用物流配送") input:checked').count():
        ok, msg = await ensure_extract_way(page)
        if not ok:
            return False, f'radio失败:{msg}'
        await asyncio.sleep(0.6)
    await ensure_no_overlay(page)
    trig = page.locator('#sell-field-tbExtractWay span.next-select').first
    await trig.click(timeout=8000)
    await asyncio.sleep(1.5)
    opt = page.locator('.next-overlay-wrapper.opened .next-menu-item', has_text=TEMPLATE).first
    if await opt.count() == 0:
        opt = page.locator('.next-overlay-wrapper.opened .options-item', has_text=TEMPLATE).first
    for _ in range(6):
        if await opt.count() > 0:
            break
        await asyncio.sleep(0.5)
    if await opt.count() == 0:
        await page.keyboard.press('Escape')
        return False, '下拉无目标模板'
    await opt.click(timeout=8000)
    await asyncio.sleep(0.8)
    st2 = await page.evaluate(STATE_JS)
    return st2['template'] == TEMPLATE, f'模板={st2["template"]!r}'


async def set_warehouse(page):
    """放入仓库 radio: 必须对 input 做 force 点击(样式化 radio 正常点击会被拦截, 2026-09-27 实证)."""
    # 复刻实证成功路径: 清弹层 → scrollIntoView → 等2s → JS直点(无视遮挡) → force 兜底
    for wait_s in (2, 5, 8, 12):
        st = await page.evaluate(STATE_JS)
        if st and st['startTime'] == '放入仓库':
            return True, '已是放入仓库'
        await asyncio.sleep(wait_s)   # 新鲜页面水合时序(2026-09-27 实证)
        await ensure_no_overlay(page)   # catProp 等步骤可能残留弹层挡点击
        await page.evaluate("""() => {
            const el = document.querySelector('#sell-field-startTime');
            if (el) el.scrollIntoView({block: 'center'});
        }""")
        await asyncio.sleep(2)
        js_ok = await page.evaluate("""() => {
            const el = document.querySelector('#sell-field-startTime');
            if (!el) return false;
            for (const w of el.querySelectorAll('label')) {
                if (/放入仓库/.test(w.textContent||'')) {
                    const i = w.querySelector('input');
                    if (i) { i.click(); return true; }
                }
            }
            return false;
        }""")
        await asyncio.sleep(1.5)
        st = await page.evaluate(STATE_JS)
        if st and st['startTime'] == '放入仓库':
            return True, f'js点击生效(等{wait_s}s)'
        inp = page.locator("#sell-field-startTime label:has-text('放入仓库') input").first
        if await inp.count() == 0:
            return False, 'NO_INPUT'
        try:
            await inp.click(force=True, timeout=8000)
        except Exception:
            pass
        await asyncio.sleep(1.5)
    st = await page.evaluate(STATE_JS)
    if st and st['startTime'] == '放入仓库':
        return True, 'force点击生效'
    return False, f'写回={st["startTime"]!r}'


async def fill_catprop_required(page, title):
    for _round in range(4):
        errs = await page.evaluate("""() => {
          const out = [];
          for (const s of document.querySelectorAll("#sell-field-catProp [id*='struct-p-']")) {
            const lab = s.querySelector(".label.required, .label[class*='required']");
            if (!lab) continue;
            const sel = s.querySelector("span.next-select");
            const cur = sel ? (sel.innerText||'').trim() : '';
            if (cur && cur !== '请选择') continue;
            out.push({label: (lab.innerText||'').replace(/[*\\s]/g,''),
                      struct: (s.id||'').match(/struct-p-\\d+/)?.[0] || s.id});
          }
          return out;
        }""")
        if not errs:
            return True, 'catProp 无必填缺失'
        fixed = 0
        for e in errs:
            if not e['struct']:
                continue
            trig = page.locator(f"#{e['struct']} span.next-select").first
            if await trig.count() == 0:
                continue
            try:
                await trig.click(timeout=6000)
            except Exception:
                continue
            opts = None
            for _ in range(8):
                await asyncio.sleep(0.5)
                opts = await page.evaluate(OPTIONS_JS)
                if opts:
                    break
            if not opts:
                await page.keyboard.press('Escape')
                continue
            pick = None
            if e['label'] == '版型':
                for val, kws in BANXING_ALIAS:
                    if val in opts and any(k in (title or '') for k in kws):
                        pick = val
                        break
                if not pick:
                    pick = '宽松' if '宽松' in opts else opts[0]
            else:
                hits = [o for o in opts if o and o in (title or '')]
                pick = hits[0] if hits else opts[0]
            opt = page.locator(f'.next-overlay-wrapper.opened .options-item[title="{pick}"], .next-overlay-wrapper.opened .next-menu-item[title="{pick}"]').first
            if await opt.count() == 0:
                opt = page.locator('.next-overlay-wrapper.opened .options-item, .next-overlay-wrapper.opened .next-menu-item').first
            await opt.click(timeout=8000)
            await asyncio.sleep(0.6)
            fixed += 1
        if not fixed:
            return False, f'catProp 未能修复: {[e["label"] for e in errs]}'
    return True, 'catProp 已清零'


async def process_one(ctx, oid):
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDITOR_URL.format(oid=oid), timeout=90000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page, timeout=90)
        if not title:
            return 'fail', '编辑器加载失败'
        log(f"  标题: {title[:32]} | 分类: {classify(title)}")
        for _ in range(2):
            await scroll_edit_page(page)
            await asyncio.sleep(1)
        await handle_recommend_dialog(page)
        await clear_overlays(page)
        await ensure_no_overlay(page)
        cat = classify(title)
        if cat == '长裤':
            cat = '休闲裤'   # 店铺分类树已改名(2026-09-27 实测)
        cok, cmsg = await set_shop_category(page, cat)
        if not cok:
            return 'fail', f'分类失败: {cmsg}'
        log(f"  分类[{cat}] ✓")
        tok, tmsg = await ensure_template(page)
        if not tok:
            return 'fail', f'模板失败: {tmsg}'
        log(f"  模板 ✓ ({tmsg})")
        cok2, cmsg2 = await fill_catprop_required(page, title)
        if not cok2:
            return 'fail', f'catProp失败: {cmsg2}'
        log(f"  catProp ✓ ({cmsg2})")
        wok, wmsg = await set_warehouse(page)
        if not wok:
            return 'fail', f'上架时间失败: {wmsg}'
        log(f"  放入仓库 ✓")
        gaps, msgs, err = await run_compliance_fill(page, title)
        if err:
            return 'fail', f'合规失败: {err}'
        if gaps:
            return 'fail', f'必填未清零: {[g["name"] for g in gaps]}'
        log(f"  合规 ✓")
        await handle_recommend_dialog(page)
        sok, smsg, risk = await click_submit(page)
        if risk:
            return 'risk', smsg
        if not sok and '超时' in smsg:
            return 'ok', '提交超时(假失败高发)'
        if not sok:
            await asyncio.sleep(2)
            board = await page.evaluate(
                "() => { const b = document.querySelector('#struct-error-board');"
                " return b ? (b.innerText||'').replace(/\\s+/g,' ').slice(0, 200) : ''; }")
            return 'fail', f'{smsg[:50]} | {board[:120]}'
        return 'ok', smsg[:60]
    except Exception as e:
        estr = str(e)
        if 'closed' in estr or 'crash' in estr.lower() or 'Target' in estr:
            return 'risk', '页面失效: ' + estr[:60]
        return 'fail', estr[:80]
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def main():
    ids = json.load(open(f'{BASE}/isv_offer_ids.json'))
    prog = load_prog()
    fixed = set(prog['fixed'])
    todo = [i for i in ids if str(i) not in fixed]
    log(f"=== ISV 铺货失败重发布: 待处理 {len(todo)}/{len(ids)} (已修 {len(fixed)})")
    if not todo:
        log('全部完成')
        sys.exit(0)
    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com", "item.upload.taobao.com", "1688.com"], log=log)
    ensure_guard_tab()
    my_ids = set(todo)
    stat = {'ok': 0, 'fail': 0}
    for i, oid in enumerate(todo):
        log(f"[{i+1}/{len(todo)}] offer {oid} ...")
        try:
            status, msg = await asyncio.wait_for(process_one(ctx, oid), timeout=240)
        except asyncio.TimeoutError:
            status, msg = 'fail', '处理超时240s'
        if status == 'ok':
            prog['fixed'].append(str(oid))
            prog['failed'].pop(str(oid), None)
            stat['ok'] += 1
            log(f"  ✓ {msg}")
        elif status == 'risk':
            log(f"  ⚠ 风控: {msg}")
            save_prog(prog)
            ensure_guard_tab()
            await b.close()
            sys.exit(42)
        else:
            prog['failed'][str(oid)] = msg
            stat['fail'] += 1
            log(f"  ✗ {msg}")
        save_prog(prog)
        await cleanup_leaked_tabs(ctx, my_ids)
        await asyncio.sleep(random.uniform(3, 5))
        if (i + 1) % 20 == 0:
            rest = random.uniform(20, 30)
            log(f"  已处理 {i+1} (✓{stat['ok']} ✗{stat['fail']}), 休息 {int(rest)}s")
            await asyncio.sleep(rest)
    log(f"=== 本轮完成: 成功={stat['ok']} 失败={stat['fail']}; 累计已修 {len(prog['fixed'])}")
    ensure_guard_tab()
    await b.close()


if __name__ == '__main__':
    asyncio.run(main())
