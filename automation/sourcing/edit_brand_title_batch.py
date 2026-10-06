#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""淘宝品牌/导购标题/主标题 AI 批量填写 — 字段函数与常量。

Task 3 只放字段函数; Task 4 在文件末尾追加枚举/主循环。
解释器固定 automation/venv/bin/python。
"""
import asyncio
import os
import random
import sys
import time
import traceback

from cdp_utils import connect_cdp
from brand_title_rules import ensure_guiruo_prefix, TITLE_MAX, dedup_targets, merge_progress
from assign_shop_category import (
    log, handle_recommend_dialog, wait_edit_ready, scroll_edit_page,
    check_listing_mode, click_submit, cleanup_leaked_tabs,
)
from compliance_filler import clear_overlays

CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"
BRAND = '瑰若'
BRAND_LABEL = '品牌'
BRAND_WRAP_ID = 'sell-field-p-20000'   # Phase 0 探路确认
# 导购标题: 必须优先 #sell-field-shopping_title; 外层 #struct-shopping_title 会抢 [id*=shopping_title]
GUIDE_SEL = '#sell-field-shopping_title, [id*="shopping_title"]'


def _wrapper_id(page, label):
    return page.evaluate(r"""(label) => {
        const els = [...document.querySelectorAll('*')];
        for (const e of els) {
            if (e.children.length === 0 && (e.innerText||'').trim() === label) {
                let c = e;
                for (let i=0;i<10;i++){ c = c.parentElement; if(!c) break;
                    if (c.classList && c.classList.contains('sell-component-info-wrapper-wrap')) return c.id; }
            }
        }
        return null;
    }""", label)


async def _set_select_value(page, label, value):
    """next-select(readonly) 用 React fiber dataSource 选值; 失败返回 (False,msg)。抄 edit_jeans_batch.fill_select。"""
    res = await page.evaluate(r"""(args) => {
        const {label, value} = args;
        const spans = document.querySelectorAll('.sell-component-info-wrapper-label span, .sell-component-info-wrapper-label');
        let lab = null;
        for (const s of spans) { if (s.children.length === 0 && (s.innerText||'').trim() === label) { lab = s; break; } }
        if (!lab) lab = [...document.querySelectorAll('*')].find(e => e.children.length===0 && (e.innerText||'').trim()===label);
        if (!lab) return {ok:false, msg:'NO_LABEL'};
        lab.scrollIntoView({block:'center'});
        let f = lab;
        for (let i=0;i<10;i++){ f=f.parentElement; if(!f)break; if(f.classList&&f.classList.contains('sell-component-info-wrapper-wrap'))break; }
        if (!f) return {ok:false, msg:'NO_WRAPPER'};
        const em = f.querySelector('.next-select-values em');
        if (em && em.textContent.trim() === value) return {ok:true, msg:'ALREADY_SET'};
        const sel = f.querySelector('.next-select');
        if (!sel) return {ok:false, msg:'NO_SELECT'};
        const key = Object.keys(sel).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
        if (!key) return {ok:false, msg:'NO_FIBER'};
        let fiber = sel[key];
        for (let i=0;i<40 && fiber;i++){
            const p = fiber.memoizedProps || fiber.pendingProps;
            if (p && typeof p.onChange === 'function') {
                const ds = p.dataSource;
                if (Array.isArray(ds) && ds.length) {
                    const opt = ds.find(o => o && o.text === value);
                    if (opt) { p.onChange(opt); return {ok:true, msg:'SET_OK'}; }
                    return {ok:false, msg:'NO_OPT:' + ds.slice(0,5).map(o=>o.text).join(',')};
                }
            }
            fiber = fiber.return;
        }
        return {ok:false, msg:'NO_ONCHANGE'};
    }""", {"label": label, "value": value})
    return bool(res.get('ok')), res.get('msg', '')


async def _read_select_value(page, label):
    return await page.evaluate(r"""(label) => {
        const els = [...document.querySelectorAll('*')];
        for (const e of els) {
            if (e.children.length === 0 && (e.innerText||'').trim() === label) {
                let c = e;
                for (let i=0;i<10;i++){ c=c.parentElement; if(!c)break;
                    if (c.classList && c.classList.contains('sell-component-info-wrapper-wrap')) {
                        const em = c.querySelector('.next-select-values em');
                        return em ? em.textContent.trim() : '';
                    } }
            }
        }
        return '';
    }""", label)


async def _try_search_pick(page, value):
    """在弹层搜索框输入 value 过滤后点选。返回 bool。品牌下拉是短列表/虚拟列表, 必须用搜索。"""
    try:
        inp = page.locator('.next-overlay-inner.next-select-popup-wrap input').last
        await inp.fill(value)
    except Exception:
        return False
    await asyncio.sleep(1.5)
    return await page.evaluate(r"""(val) => {
        const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        for (const p of document.querySelectorAll('.next-overlay-inner.next-select-popup-wrap')) {
            if (!vis(p)) continue;
            for (const e of p.querySelectorAll('.options-item[title]')) {
                const t = e.getAttribute('title') || (e.innerText || '').trim();
                if (t === val) { e.click(); return true; }
            }
        }
        return false;
    }""", value)


async def _pick_option_with_scroll(page, value, tries=20):
    """在已展开的 next-select 弹层里找 value。
    2026-10-06 修复: 品牌下拉是"可搜索虚拟列表"(列表本身很短、常不含目标品牌),
    仅滚动加载永远命中不了 → 先往弹层搜索框输入 value 过滤点选, 失败再退回逐格滚动。
    实测 item 1072792950267: 初始仅 14 项不含「瑰若」, 输入后选项=['瑰若'] 且回显=瑰若。

    实测(2026-10-05 item 1082404842251)品牌下拉真实 DOM 与 brief 假设不同:
    弹层 `.next-overlay-inner.next-select-popup-wrap` 内含可滚动 `.options-content`,
    选项为自定义 `.options-item[title]`(不是 .next-menu-item/li)。故在原选择器上补齐并限定在
    品牌弹层内点击; 滚动也补上 `.options-content`(否则滚错容器, 永远加载不到后续项)。"""
    if await _try_search_pick(page, value):
        return True
    for _ in range(tries):
        clicked = await page.evaluate(r"""(val) => {
            const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
            let scope = null;
            for (const p of document.querySelectorAll('.next-overlay-inner.next-select-popup-wrap'))
                if (vis(p) && p.querySelector('.options-content')) { scope = p; break; }
            const root = scope || document;
            for (const e of root.querySelectorAll('.options-item[title], .next-menu-item, .next-select-menu-item, .next-tree-node-label')) {
                if (!vis(e)) continue;
                const t = (e.getAttribute && e.getAttribute('title')) || (e.innerText||'').trim();
                if (t === val) { e.click(); return true; }
            }
            for (const e of root.querySelectorAll('li')) {
                if (vis(e) && (e.innerText||'').trim() === val) { e.click(); return true; }
            }
            return false;
        }""", value)
        if clicked:
            return True
        await page.evaluate(r"""() => {
            for (const menu of document.querySelectorAll('.options-content, .next-select-menu, .next-overlay-inner.next-select-popup-wrap, .next-virtual-list')) {
                if (menu.scrollHeight > menu.clientHeight) menu.scrollTop = menu.scrollHeight;
            }
        }""")
        await asyncio.sleep(0.8)
    return False


async def set_brand(page, brand=BRAND):
    await page.keyboard.press('Escape')
    await asyncio.sleep(0.3)
    ok, msg = await _set_select_value(page, BRAND_LABEL, brand)
    if not ok:
        wid = await _wrapper_id(page, BRAND_LABEL)
        if wid:
            try:
                sel = page.locator(f'#{wid} .next-select').first
                await sel.hover(timeout=3000)
                try:
                    await page.locator(f'#{wid} .next-select-clear').first.click(timeout=1500)
                except Exception:
                    pass
                await sel.click(timeout=3000)
                await asyncio.sleep(1.2)
                if not await _pick_option_with_scroll(page, brand):
                    return False, f'品牌UI选择失败: {brand} 滚动加载后仍未找到'
                ok = True
            except Exception as e:
                return False, f'品牌UI选择失败: {str(e)[:50]}'
    await asyncio.sleep(0.5)
    got = await _read_select_value(page, BRAND_LABEL)
    if got != brand:
        return False, f'品牌写回校验失败: 期望{brand} 实际{got}'
    return True, f'品牌={brand}'


async def read_main_title(page):
    return await page.evaluate("""() => {
        const i = document.querySelector('#sell-field-title input, input[placeholder*="标题"], input[name*="title"]');
        return i ? i.value : '';
    }""")


async def ai_guide_title(page):
    """导购标题 AI: 清空 → 点 .ai-icon → 等「立即使用」→ 点击。抄 edit_jeans_batch.fill_ai_guide_title。"""
    await page.evaluate(r"""(sel) => {
        const w = document.querySelector(sel); if (!w) return;
        const inp = w.querySelector('input'); if (!inp) return;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(inp, '');
        inp.dispatchEvent(new Event('input', {bubbles:true}));
        inp.dispatchEvent(new Event('change', {bubbles:true}));
        inp.dispatchEvent(new Event('blur', {bubbles:true}));
    }""", GUIDE_SEL)
    await asyncio.sleep(0.5)
    clicked = await page.evaluate(r"""(sel) => {
        let w = document.querySelector(sel);
        if (!w) {
            const lab = [...document.querySelectorAll('*')].find(e => e.children.length===0 && (e.innerText||'').trim()==='导购标题');
            if (!lab) return false;
            let c = lab;
            for (let i=0;i<6;i++){ c=c.parentElement; if(!c)break; const ai=c.querySelector('.ai-icon'); if(ai){ai.click();return true;} }
            return false;
        }
        const ai = w.querySelector('.ai-icon'); if (ai) { ai.click(); return true; }
        return false;
    }""", GUIDE_SEL)
    if not clicked:
        return False, '导购标题 ai-icon 未找到'
    for _ in range(15):
        await asyncio.sleep(1)
        ok = await page.evaluate(r"""() => {
            const els = [...document.querySelectorAll('.adopt-btn, span, button')];
            for (const e of els) {
                if (e.getBoundingClientRect().width > 0 && (e.textContent||'').trim() === '立即使用') { e.click(); return true; }
            }
            return false;
        }""")
        if ok:
            await asyncio.sleep(1.5)
            return True, '导购标题已采纳'
    return False, 'AI导购标题「立即使用」未出现(超时)'


async def ai_main_title(page, prefix=BRAND):
    """主标题 AI: 在标题字段容器内找 AI 触发 → 采纳 → 强制 prefix 开头。
    通用定位(不依赖单一 class): .ai-icon, 或容器内文本匹配 AI/智能/生成 的可点击元素。"""
    cur = await read_main_title(page)
    triggered = await page.evaluate(r"""() => {
        const w = document.querySelector('#sell-field-title') || document.querySelector('input[placeholder*="标题"]')?.closest('.sell-component-info-wrapper-wrap');
        if (!w) return false;
        let ai = w.querySelector('.ai-icon');
        if (ai) { ai.click(); return true; }
        const cand = [...w.querySelectorAll('button,span,div,i')].find(e => {
            const t = (e.innerText||'').trim();
            return e.children.length === 0 && t.length < 12 && /AI|智能|生成|帮我写/.test(t);
        });
        if (cand) { cand.click(); return true; }
        return false;
    }""")
    if not triggered:
        return False, '主标题AI触发元素未找到'
    # 实测(2026-10-05 item 1074565668768): 主标题 AI 触发后展开内联「标题推荐」面板,
    # 采纳按钮文本=「全部采用」(.adopt-all-btn), 不是导购标题那套「立即使用」; 兼容其余文案。
    applied = False
    for _ in range(15):
        await asyncio.sleep(1)
        applied = await page.evaluate(r"""() => {
            const re = /全部采用|立即使用|采纳|使用该标题|应用/;
            const w = document.querySelector('#sell-field-title');
            const global = document.querySelectorAll('.adopt-all-btn, .adopt-btn, button, span');
            const local = w ? w.querySelectorAll('.adopt-all-btn, .adopt-btn, button, span') : null;
            const lists = local ? [local, global] : [global];
            for (const list of lists) {
                for (const e of list) {
                    if (e.getBoundingClientRect().width > 0 && re.test((e.textContent||'').trim())) { e.click(); return true; }
                }
            }
            return false;
        }""")
        if applied:
            break
    if not applied:
        return False, '主标题AI采纳按钮未出现(超时)'
    await asyncio.sleep(1.5)
    new_title = await read_main_title(page)
    fixed = ensure_guiruo_prefix(new_title, prefix=prefix, max_len=TITLE_MAX)
    if fixed != new_title:
        await page.evaluate(r"""(val) => {
            const inp = document.querySelector('#sell-field-title input, input[placeholder*="标题"], input[name*="title"]');
            if (!inp) return;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, val);
            inp.dispatchEvent(new Event('input', {bubbles:true}));
            inp.dispatchEvent(new Event('change', {bubbles:true}));
        }""", fixed)
        await asyncio.sleep(0.5)
    final = await read_main_title(page)
    if not final.startswith(prefix):
        return False, f'主标题前缀校验失败: {final[:20]}'
    return True, f'主标题={final[:24]}'


# ---------------------------------------------------------------------------
# Task 4: 清单采集 + process_one + 主循环 + 进度
# ---------------------------------------------------------------------------
import fcntl
import json

TARGETS_FILE = os.path.join(BASE, "brand_title_targets.jsonl")
PROGRESS_FILE = os.path.join(BASE, "brand_title_progress.json")
LIST_URLS = {
    # 2026-10-06 修复: 出售中正确路由是 SellManage/on_sale(986件);
    # 原用 SellManage/sold_out 实为含仓库项的大视图(4228), 会让 in_stock 全成其子集被 dedup 清空。
    'onsale': "https://myseller.taobao.com/home.htm/SellManage/on_sale?current=1&pageSize=20",
    'warehouse': "https://myseller.taobao.com/home.htm/SellManage/in_stock?current=1&pageSize=20",
}


async def _apply_shop_cat_filter(page, cat_text):
    """「店铺分类」筛选: 先点「展开」, 再开 input#queryShopCategoryId 的 next-select, 选 cat_text(tree-select)。
    返回 (ok,msg)。选择器来自 Phase 0 探路。
    2026-10-06 修复: 必须点 .next-tree-node-inner(role=treeitem) 才写入组件值;
    点 .next-tree-node-label(纯文本 div) 是假阳性(选后回显为空、搜索不生效, 实测 共4228→共1725 未触发)。
    选后读回 .next-select-values em 校验, 不再只信 picked。"""
    await page.evaluate(r"""() => {
        for (const e of document.querySelectorAll('button,span,a,div')) {
            if (e.children.length === 0 && (e.innerText||'').trim() === '展开') { e.click(); return; }
        }
    }""")
    await asyncio.sleep(1.0)
    opened = await page.evaluate(r"""() => {
        const inp = document.querySelector('input#queryShopCategoryId');
        const box = inp ? (inp.closest('.next-select') || inp.parentElement) : null;
        if (!box) return false;
        const trig = box.querySelector('.next-select-trigger') || box;
        trig.click(); return true;
    }""")
    if not opened:
        return False, '店铺分类筛选下拉未找到(input#queryShopCategoryId)'
    await asyncio.sleep(1.5)
    picked = await page.evaluate(r"""(cat) => {
        for (const n of document.querySelectorAll('.next-tree-node')) {
            const inner = n.querySelector('.next-tree-node-inner') || n;
            const label = n.querySelector('.next-tree-node-label');
            const txt = (label ? label.innerText : (n.innerText || '')).trim();
            if (txt === cat && inner.getBoundingClientRect().width > 0) { inner.click(); return true; }
        }
        return false;
    }""", cat_text)
    await asyncio.sleep(1.5)
    if not picked:
        return False, f'店铺分类选项未找到: {cat_text}'
    shown = await page.evaluate(r"""() => {
        const inp = document.querySelector('input#queryShopCategoryId');
        const box = inp && inp.closest('.next-select');
        const em = box ? box.querySelector('.next-select-values em') : null;
        return em ? (em.getAttribute('title') || em.innerText || '').trim() : '';
    }""")
    if shown != cat_text:
        return False, f'店铺分类未写入(回显={shown!r}, 期望={cat_text!r})'
    return True, f'filter set (回显={shown})'


async def _collect_pages(page):
    items, seen = [], set()
    for pageno in range(1, 260):
        rows = await page.evaluate(r"""() => {
            const out = [];
            for (const tr of document.querySelectorAll('tr.next-table-row')) {
                const t = tr.innerText || '';
                const m = t.match(/ID:(\d+)/);
                const a = tr.querySelector('a.title-link');
                if (m && a) out.push({itemId: m[1], title: a.textContent.trim().slice(0, 120)});
            }
            return out;
        }""")
        for r in rows:
            if r['itemId'] not in seen:
                seen.add(r['itemId']); items.append(r)
        nxt = await page.evaluate(r"""() => {
            for (const b of document.querySelectorAll('button')) {
                if ((b.textContent||'').trim() === '下一页' && !b.disabled && b.getBoundingClientRect().width > 10) { b.click(); return true; }
            }
            return false;
        }""")
        if not nxt:
            break
        await asyncio.sleep(5)
    return items


async def enumerate_targets(ctx, cat_text):
    out = []
    for pool, url in LIST_URLS.items():
        page = await ctx.new_page()
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=40000)
            await asyncio.sleep(10)
            await clear_overlays(page)
            ok, msg = await _apply_shop_cat_filter(page, cat_text)
            log(f"[{pool}] 筛选: {msg}")
            if not ok:
                raise RuntimeError(msg)
            await page.evaluate(r"""() => {
                for (const b of document.querySelectorAll('button')) {
                    if ((b.textContent||'').trim() === '搜索') { b.click(); return; }
                }
            }""")
            await asyncio.sleep(5)
            await clear_overlays(page)
            rows = await _collect_pages(page)
            for r in rows:
                r['pool'] = pool
            log(f"[{pool}] 采集 {len(rows)} 个")
            out.extend(rows)
        finally:
            await page.close()
    # 护栏: 出售中/仓库中两池应基本不相交。2026-10-06 曾因 sold_out 路由实为含仓库项的大视图,
    # 使 in_stock 全成其子集被 dedup 清空 → 交集占比过高即报错, 拒绝写坏清单。
    by_pool = {}
    for r in out:
        by_pool.setdefault(r['pool'], set()).add(str(r['itemId']))
    pools = list(by_pool)
    for i in range(len(pools)):
        for j in range(i + 1, len(pools)):
            a, b = by_pool[pools[i]], by_pool[pools[j]]
            if a and b and len(a & b) / min(len(a), len(b)) > 0.5:
                raise RuntimeError(
                    f"两池 {pools[i]}/{pools[j]} 交集过大({len(a & b)}/{min(len(a), len(b))}), "
                    f"疑似路由/筛选错误, 拒绝写清单")
    return dedup_targets(out)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            d = json.load(open(PROGRESS_FILE, encoding='utf-8'))
            d.setdefault('done', []); d.setdefault('failed', {}); d.setdefault('skipped', [])
            return d
        except Exception:
            pass
    return {'done': [], 'failed': {}, 'skipped': []}


def save_progress(prog):
    lock = open(PROGRESS_FILE + '.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        merged = merge_progress(load_progress(), prog)
        tmp = PROGRESS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PROGRESS_FILE)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def build_todo(targets, prog, retry_failed=False, start=0, limit=0, test=False, ids=None):
    done, skipped = set(prog['done']), set(prog['skipped'])
    failed = set(prog['failed'].keys())
    ids_set = set(ids) if ids else None
    todo = []
    for r in targets[start:]:
        iid = str(r['itemId'])
        if iid in done:
            continue
        if iid in skipped and not (ids_set and iid in ids_set):
            continue
        if iid in failed and not (retry_failed or (ids_set and iid in ids_set)):
            continue
        todo.append(r)
    if ids_set:
        todo = [r for r in todo if str(r['itemId']) in ids_set]
    todo.sort(key=lambda r: 0 if r.get('pool') == 'onsale' else 1)
    if test:
        todo = todo[:1]
    elif limit:
        todo = todo[:limit]
    return todo


async def process_one(ctx, rec):
    item_id = str(rec['itemId'])
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), wait_until='domcontentloaded', timeout=60000)
        title = await wait_edit_ready(page)
        if not title:
            return 'skip', '编辑页加载超时(表单未水合)'
        await handle_recommend_dialog(page)
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        await handle_recommend_dialog(page)
        await clear_overlays(page)
        lm = await check_listing_mode(page)
        if not lm.get('ok') or lm.get('txt') not in ('放入仓库', '立刻上架'):
            return 'skip', f'上架状态异常: {lm.get("txt")}'
        bok, bmsg = await set_brand(page, BRAND)
        if not bok:
            return 'fail', bmsg
        gok, gmsg = await ai_guide_title(page)
        if not gok:
            return 'fail', gmsg
        mok, mmsg = await ai_main_title(page, prefix=BRAND)
        if not mok:
            return 'fail', mmsg
        sok, smsg, risk = await click_submit(page)
        if risk:
            return 'risk', smsg
        if not sok:
            return 'fail', f'提交失败: {smsg}'
        return 'ok', f'{bmsg} | {gmsg} | {mmsg} | {smsg}'
    except Exception as e:
        estr = str(e)
        if 'Execution context was destroyed' in estr or 'Navigation' in estr:
            return 'fail', '提交时页面跳转, 待重试复核'
        if 'closed' in estr or 'Target' in estr or 'crash' in estr.lower():
            return 'risk', '页面已失效: ' + estr[:60]
        return 'fail', estr[:80]
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def main():
    args = sys.argv[1:]
    cat_text = '家居服/睡衣'  # Phase 0 探路确认的真实下拉文本
    if '--cat' in args:
        cat_text = args[args.index('--cat') + 1]
    test = '--test' in args
    enumerate_only = '--enumerate' in args
    retry_failed = '--retry-failed' in args
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else 0
    start = int(args[args.index('--start') + 1]) if '--start' in args else 0
    ids = None
    if '--ids' in args:
        ids = [s for s in (x.strip() for x in args[args.index('--ids') + 1].split(',')) if s]

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    try:
        if enumerate_only or not os.path.exists(TARGETS_FILE):
            targets = await enumerate_targets(ctx, cat_text)
            with open(TARGETS_FILE, 'w', encoding='utf-8') as f:
                for r in targets:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            log(f"清单写入 {TARGETS_FILE}: {len(targets)} 个")
            if enumerate_only:
                return
        else:
            targets = [json.loads(l) for l in open(TARGETS_FILE, encoding='utf-8') if l.strip()]
        prog = load_progress()
        todo = build_todo(targets, prog, retry_failed, start, limit, test, ids)
        my_ids = {str(r['itemId']) for r in todo}
        log(f"清单 {len(targets)}, done {len(prog['done'])}, failed {len(prog['failed'])}, skipped {len(prog['skipped'])}, 本次 {len(todo)}")
        for i, rec in enumerate(todo):
            iid = str(rec['itemId'])
            log(f"[{i+1}/{len(todo)}] {iid} ({rec.get('pool')}) ...")
            try:
                status, msg = await asyncio.wait_for(process_one(ctx, rec), timeout=300)
            except asyncio.TimeoutError:
                status, msg = 'fail', '处理超时300s'
            if status == 'ok':
                prog['done'].append(iid); prog['failed'].pop(iid, None)
                log(f"  ✓ {msg}")
            elif status == 'risk':
                log(f"  ⚠ 风控: {msg}")
                save_progress(prog)
                await b.close()
                sys.exit(42)
            elif status == 'skip':
                if iid not in prog['skipped']:
                    prog['skipped'].append(iid)
                prog['failed'].pop(iid, None)
                log(f"  ⏭ {msg}")
            else:
                prog['failed'][iid] = {'error': msg, 'pool': rec.get('pool')}
                log(f"  ✗ {msg}")
            save_progress(prog)
            await cleanup_leaked_tabs(ctx, my_ids)
            await asyncio.sleep(random.uniform(3, 5))
            if (i + 1) % 30 == 0:
                await asyncio.sleep(random.uniform(25, 35))
            if test:
                break
        log(f"完成: done={len(prog['done'])} failed={len(prog['failed'])} skipped={len(prog['skipped'])}")
    finally:
        try:
            await b.close()
        except Exception:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log('手动中断')
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
