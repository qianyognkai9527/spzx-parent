#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""美甲最小流程批量(2026-09-26 与用户手动流程对齐):
勾配送方式 → 选运费模板(一件包邮--浙江杭州) → 填必填(款式等, filler) → 勾店铺分类 → 提交.
红线: 不动主图/不改价/不清颜色/不删视频 (改价清色会触发平台重审, 翻出盗图等错误, 2026-09-26 实证).
进度: shop_cat_v2_progress.json (成功→done; 图被标记→留 skipped + nail_imgflag.json=待换图名单).
退出码: 0=本轮完成, 42=风控(wrapper 冷却重试), 1=异常."""
import asyncio
import random
import sys
import time

from cdp_utils import connect_cdp
from assign_shop_category import (
    wait_edit_ready, scroll_edit_page, handle_recommend_dialog,
    ensure_extract_way, set_shop_category, click_submit, cleanup_leaked_tabs, log,
    load_plan,
)
from assign_shop_category_v2 import (
    ensure_guard_tab, verify_by_reload, run_compliance_fill,
    load_progress, save_progress,
)
from compliance_filler import clear_overlays, ensure_no_overlay

CDP_PORT = 9222
CATEGORY = '美甲'
TEMPLATE = '一件包邮--浙江杭州'
EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"
BASE = '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing'
IMGFLAG_FILE = f'{BASE}/nail_imgflag.json'
FAILCNT_FILE = f'{BASE}/nail_failcount.json'

STATE_JS = """() => {
  const el = document.querySelector('#sell-field-tbExtractWay');
  if (!el) return null;
  const radio = [...el.querySelectorAll('label')].find(l => /使用物流配送/.test(l.textContent||''));
  const rc = radio && radio.querySelector('input') ? radio.querySelector('input').checked : null;
  const sel = el.querySelector('span.next-select');
  const inp = el.querySelector('input');
  return {radioChecked: rc, selectText: sel ? (sel.innerText||'').trim() : null,
          inputValue: inp ? (inp.value||'') : null};
}"""

CAT_JS = """() => {
  const box = document.querySelector('#sell-field-shopcat');
  return box ? [...box.querySelectorAll('.next-tag')].map(t => t.textContent.trim()) : [];
}"""


def load_json(path, default):
    import json, os
    if not os.path.exists(path):
        return default
    try:
        return json.load(open(path))
    except Exception:
        return default


def dump_json(path, data):
    import json
    json.dump(data, open(path, 'w'), ensure_ascii=False, indent=1)


async def ensure_template(page):
    st = await page.evaluate(STATE_JS)
    if st is None:
        return False, 'NO_ZONE'
    if st['selectText'] == TEMPLATE or TEMPLATE in (st['inputValue'] or ''):
        return True, '模板已是目标值'
    if not st['radioChecked']:
        ok, msg = await ensure_extract_way(page)
        if not ok:
            return False, f'radio失败:{msg}'
        await asyncio.sleep(0.6)
    await ensure_no_overlay(page)
    zone = page.locator('#sell-field-tbExtractWay')
    trig = zone.locator('[class*="template"] span.next-select, span.next-select').first
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
    ok = TEMPLATE in (st2['selectText'] or '') or TEMPLATE in (st2['inputValue'] or '')
    return ok, f'模板写回={st2["selectText"]!r}'


async def process_one_minimal(ctx, item_id):
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), timeout=60000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page)
        if not title:
            return 'fail', '页面加载超时'
        rh, m = await handle_recommend_dialog(page)
        if rh:
            log(f"  · {m}")
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        await handle_recommend_dialog(page)
        await clear_overlays(page)
        await ensure_no_overlay(page)
        cur = await page.evaluate(CAT_JS)
        if CATEGORY in cur:
            return 'ok', '分类已是美甲(他人/前置已设, 无需提交)'
        tok, tmsg = await ensure_template(page)
        if not tok:
            return 'fail', f'模板设置失败: {tmsg}'
        gaps, msgs, err = await run_compliance_fill(page, title)
        if err:
            return 'fail', f'合规填充失败: {err}'
        if gaps:
            return 'fail', f'必填未清零: {[g["name"] for g in gaps]}'
        cok, cmsg = await set_shop_category(page, CATEGORY)
        if not cok:
            return 'fail', f'分类设置失败: {cmsg}'
        rh, m = await handle_recommend_dialog(page)
        if rh:
            log(f"  · {m}")
        sok, smsg, risk = await click_submit(page)
        if risk:
            return 'risk', smsg
        if not sok and '超时' in smsg:
            vok, vmsg = await verify_by_reload(ctx, item_id, CATEGORY)
            if vok:
                return 'ok', vmsg
            return 'fail', f'提交超时且复核未过({vmsg})'
        if not sok:
            if 'PIC_STEAL' in smsg or '主图' in smsg or '1:1' in smsg:
                return 'imgfail', smsg[:50]
            return 'fail', smsg[:80]
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
    plan = load_plan()
    prog = load_progress()
    done = set(map(str, prog['done']))
    skipped = set(map(str, prog['skipped']))
    imgflag = set(load_json(IMGFLAG_FILE, []))
    failcnt = load_json(FAILCNT_FILE, {})
    todo = [str(it['itemId']) for it in plan
            if it.get('category') == CATEGORY and str(it['itemId']) in skipped
            and str(it['itemId']) not in done and str(it['itemId']) not in imgflag
            and int(failcnt.get(str(it['itemId']), 0)) < 3]
    log(f"=== 美甲最小流程启动: 待处理 {len(todo)} (imgflag排除{len(imgflag)}, 深度失败排除{sum(1 for k,v in failcnt.items() if v>=3)})")
    if not todo:
        log('无待处理, 退出')
        sys.exit(0)
    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    ensure_guard_tab()
    stat = {'ok': 0, 'imgfail': 0, 'fail': 0}
    my_ids = set(todo)
    for i, iid in enumerate(todo):
        log(f"[{i+1}/{len(todo)}] {iid} ...")
        try:
            status, msg = await asyncio.wait_for(process_one_minimal(ctx, iid), timeout=180)
        except asyncio.TimeoutError:
            status, msg = 'fail', '处理超时180s'
        if status == 'ok':
            prog['done'].append(iid)
            if iid in prog['skipped']:
                prog['skipped'].remove(iid)
            prog['failed'].pop(iid, None)
            stat['ok'] += 1
            log(f"  ✓ {msg}")
        elif status == 'imgfail':
            imgflag.add(iid)
            dump_json(IMGFLAG_FILE, sorted(imgflag))
            stat['imgfail'] += 1
            log(f"  ⏭ 主图被标记→待换图名单")
        elif status == 'risk':
            log(f"  ⚠ 风控: {msg}")
            save_progress(prog)
            ensure_guard_tab()
            await b.close()
            sys.exit(42)
        else:
            stat['fail'] += 1
            failcnt[iid] = failcnt.get(iid, 0) + 1
            dump_json(FAILCNT_FILE, failcnt)
            log(f"  ✗ {msg}")
        save_progress(prog)
        await cleanup_leaked_tabs(ctx, my_ids)
        await asyncio.sleep(random.uniform(3, 5))
        if (i + 1) % 30 == 0:
            rest = random.uniform(25, 35)
            log(f"  已处理 {i+1} (✓{stat['ok']} ⏭{stat['imgfail']} ✗{stat['fail']}), 休息 {int(rest)}s")
            await asyncio.sleep(rest)
    log(f"=== 本轮完成: 成功={stat['ok']} 待换图={stat['imgfail']} 失败={stat['fail']}; 剩余待处理={len(todo)-sum(stat.values())}")
    ensure_guard_tab()
    await b.close()


if __name__ == '__main__':
    asyncio.run(main())
