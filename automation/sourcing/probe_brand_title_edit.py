#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 0 只读探路: dump 列表页「店铺分类」筛选 + 编辑页字段/AI 元素, 供校准 selector。

只读、不提交、不改商品。产出 `probe_brand_title_out.json`, 供 Task 3/4 校准
set_brand / ai_guide_title / ai_main_title / enumerate_targets 的选择器。

用法:
  venv/bin/python probe_brand_title_edit.py --list          # 只探列表页(店铺分类下拉)
  venv/bin/python probe_brand_title_edit.py --item <itemId>  # 探编辑页字段/AI 元素
  venv/bin/python probe_brand_title_edit.py --item <id> --list  # 两者都探
  不带参数默认 --list。

Phase 0 结论(2026-10-05 实测, item 1074565668768):
  - 列表页「店铺分类」在筛选区「展开」之后; 下拉是 tree-select, input#queryShopCategoryId;
    真实选项文本「家居服/睡衣」(非睡衣/家居服), 选项节点 .next-tree-node-label.next-tree-node-label-selectable。
  - 编辑页主标题 AI 触发存在: #sell-field-title .ai-icon (宝贝标题旁)。
    导购标题 AI: #sell-field-shopping_title .ai-icon。
  - 品牌容器: #sell-field-p-20000 (class sell-component-info-wrapper-wrap)。
  - 标题上限: 主标题「最多允许输入30个汉字（60字符）」; 导购标题「最多输入30字符（15个汉字）」。
"""
import asyncio
import json
import os
import sys
import time

from cdp_utils import connect_cdp

CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_brand_title_out.json")
SOLD_OUT_URL = "https://myseller.taobao.com/home.htm/SellManage/sold_out?current=1&pageSize=20"
EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"

# 列表页: 扫「店铺分类」标签 + 关联 select (input#queryShopCategoryId)
JS_LIST_SCAN = r"""() => {
    const vis = (e) => { const r = e.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight + 3000; };
    const cls = (e) => (e && e.className || '').toString().slice(0, 160);
    const out = {url: location.href, title: document.title, shopcat_labels: [],
                 selects: [], filter_buttons: [], shopcat_candidate: null, expanded: null};

    // 1) 文本含「店铺分类」的叶子节点
    for (const e of document.querySelectorAll('*')) {
        const t = (e.textContent || '').trim();
        if (e.children.length === 0 && t.length < 20 && t.indexOf('店铺分类') >= 0) {
            out.shopcat_labels.push({tag: e.tagName, id: e.id, cls: cls(e), text: t, visible: vis(e)});
        }
    }

    // 2) 页面可见 .next-select
    const allSel = [...document.querySelectorAll('.next-select')];
    allSel.forEach((s, i) => {
        if (!vis(s)) return;
        const inp = s.querySelector('input');
        out.selects.push({idx: i, id: s.id, cls: cls(s),
            input_id: inp ? inp.id : '', input_name: inp ? (inp.getAttribute('name') || '') : '',
            text: (s.innerText || '').trim().slice(0, 60)});
    });

    // 3) 筛选区按钮(展开/收起/筛选)
    for (const e of document.querySelectorAll('button, span, a, div')) {
        const t = (e.textContent || '').trim();
        if (e.children.length === 0 && t.length < 12 && /^(展开|收起|筛选|更多筛选)$/.test(t) && vis(e)) {
            out.filter_buttons.push({tag: e.tagName, cls: cls(e), text: t});
        }
    }
    const exp = out.filter_buttons.find(b => b.text === '收起');
    out.expanded = !!exp;

    // 4) 店铺分类 select: 优先 input#queryShopCategoryId, 否则按标签向上找
    let cand = null, via = '';
    const inp = document.getElementById('queryShopCategoryId');
    if (inp) { cand = inp.closest('.next-select'); via = 'input#queryShopCategoryId'; }
    if (!cand) {
        for (const lab of document.querySelectorAll('span,div,label')) {
            const t = (lab.textContent || '').trim();
            if (!(lab.children.length === 0 && t.length < 20 && t.indexOf('店铺分类') >= 0)) continue;
            let c = lab, hit = null;
            for (let i = 0; i < 12 && c; i++) {
                const sels = c.querySelectorAll('.next-select');
                if (sels.length) { hit = sels[0]; break; }
                c = c.parentElement;
            }
            if (hit) { cand = hit; via = 'label:' + t; break; }
        }
    }
    if (cand) {
        cand.scrollIntoView({block: 'center'});
        const r = cand.getBoundingClientRect();
        const ci = cand.querySelector('input');
        out.shopcat_candidate = {tag: cand.tagName, id: cand.id, cls: cls(cand),
            input_id: ci ? ci.id : '', input_name: ci ? (ci.getAttribute('name') || '') : '',
            text: (cand.innerText || '').trim().slice(0, 60),
            x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), found_via: via};
    }
    return out;
}"""

# 点开下拉后 dump 选项(兼容 next-menu / next-tree-select 两种结构)
JS_DUMP_OPTIONS = r"""() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const cls = (e) => (e && e.className || '').toString().slice(0, 160);
    const out = {opened_menu: false, menu_containers: [], options: [], option_texts: []};
    for (const c of document.querySelectorAll(
            '.next-overlay-inner.next-select-popup-wrap, .next-select-menu-wrapper, .next-menu, .next-overlay-inner, .next-tree-select')) {
        if (!vis(c)) continue;
        out.opened_menu = true;
        out.menu_containers.push({tag: c.tagName, id: c.id, cls: cls(c),
            text: (c.innerText || '').trim().slice(0, 200)});
    }
    // .next-tree-node-label 与 .next-menu-item 互斥, 避免同一选项重复
    const nodes = [...document.querySelectorAll('.next-menu-item, [role=option], .next-tree-node-label, .next-select-menu-item')];
    let idx = 0;
    for (const n of nodes) {
        if (!vis(n)) continue;
        const t = (n.innerText || '').trim();
        if (!t) continue;
        out.options.push({idx: idx++, tag: n.tagName, cls: cls(n), text: t.slice(0, 40),
            selected: /selected|active|checked/.test(cls(n)),
            suggested: '.' + ((n.className || '').toString().trim().split(/\s+/).join('.')).slice(0, 80)});
    }
    out.option_texts = [...new Set(out.options.map(o => o.text))];
    return out;
}"""

# 编辑页: dump 主标题/品牌/导购标题容器 + AI 元素(含归属字段) + 长度上限 + 品牌可选项
JS_EDIT_SCAN = r"""() => {
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const cls = (e) => (e && e.className || '').toString().slice(0, 160);
    const wrapMeta = (e) => e ? {tag: e.tagName, id: e.id, cls: cls(e), text: (e.innerText || '').trim().slice(0, 200)} : null;
    const out = {url: location.href, page_title: document.title,
        title_container: null, title_input: null, brand_container: null, brand_select: null,
        brand_options_sample: [], brand_options_len: null, brand_has_guiruo: null,
        shopping_container: null, shopping_wrapper_present: false, struct_present: false,
        shopping_input: null, ai_icons: [], ai_like_texts: [], counters: []};

    out.title_container = wrapMeta(document.querySelector('#sell-field-title'));
    const ti = document.querySelector('#sell-field-title input, input[placeholder*="标题"], input[name*="title"]');
    if (ti) out.title_input = {value: ti.value, placeholder: ti.getAttribute('placeholder') || '',
        maxLength: ti.maxLength, name: ti.getAttribute('name') || ''};

    out.shopping_wrapper_present = !!document.querySelector('#sell-field-shopping_title');
    out.struct_present = !!document.querySelector('#struct-shopping_title');
    out.shopping_container = wrapMeta(document.querySelector('#sell-field-shopping_title')) ||
                             wrapMeta(document.querySelector('#struct-shopping_title'));
    const si = document.querySelector('#sell-field-shopping_title input, [id*="shopping_title"] input');
    if (si) out.shopping_input = {id: si.id, value: si.value, placeholder: si.getAttribute('placeholder') || ''};

    // 品牌容器: 找叶子文本「品牌」, 逐级向上到 sell-component-info-wrapper-wrap
    let brand = null;
    for (const e of document.querySelectorAll('*')) {
        if (!(e.children.length === 0 && (e.innerText || '').trim() === '品牌')) continue;
        let c = e;
        for (let i = 0; i < 12 && c; i++) { c = c.parentElement; if (!c) break;
            if (c.classList && c.classList.contains('sell-component-info-wrapper-wrap')) { brand = c; break; } }
        if (brand) break;
    }
    out.brand_container = wrapMeta(brand);
    if (brand) {
        const sel = brand.querySelector('.next-select');
        if (sel) {
            out.brand_select = {id: sel.id, cls: cls(sel)};
            const key = Object.keys(sel).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
            if (key) {
                let fiber = sel[key];
                for (let i = 0; i < 60 && fiber; i++) {
                    const p = fiber.memoizedProps || fiber.pendingProps;
                    if (p && Array.isArray(p.dataSource)) {
                        out.brand_options_len = p.dataSource.length;   // 仅已加载页(virtual), 非全量
                        out.brand_options_sample = p.dataSource.slice(0, 8).map(o => o && (o.text || o.label || String(o.children)));
                        out.brand_has_guiruo = p.dataSource.some(o => o && (o.text || o.label) === '瑰若');
                        break;
                    }
                    fiber = fiber.return;
                }
            }
        }
    }

    // 所有可见 .ai-icon: 记录最近带 id 的祖先(即所属字段容器)
    const nearestId = (e) => { let c = e;
        for (let i = 0; i < 16 && c; i++) { c = c.parentElement; if (!c) break; if (c.id) return c.id; }
        return null; };
    for (const e of document.querySelectorAll('.ai-icon, [class*=ai-icon], [class*=" ai-"], [class^="ai-"]')) {
        if (!vis(e)) continue;
        out.ai_icons.push({tag: e.tagName, id: e.id, cls: cls(e), html: e.outerHTML.slice(0, 160),
            nearest_id_ancestor: nearestId(e)});
    }
    // 文本形似 AI 触发元素的可点击叶子(AI 按钮兜底)
    const seen = new Set();
    for (const e of document.querySelectorAll('button, span, div, i, a')) {
        const t = (e.innerText || '').trim();
        if (e.children.length === 0 && t.length > 0 && t.length < 12 && /AI|智能|生成|帮我/.test(t) && vis(e)) {
            const k = t + '|' + cls(e);
            if (!seen.has(k)) { seen.add(k);
                out.ai_like_texts.push({text: t, tag: e.tagName, cls: cls(e), nearest_id_ancestor: nearestId(e)}); }
        }
    }

    // 长度计数器(如 52/60)
    for (const e of document.querySelectorAll('*')) {
        const t = (e.innerText || '').trim();
        if (e.children.length === 0 && t.length < 12 && /^\d+\s*\/\s*\d+$/.test(t) && vis(e)) {
            out.counters.push({text: t, tag: e.tagName, cls: cls(e), nearest_id_ancestor: nearestId(e)});
        }
    }
    return out;
}"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def close_overlays(page):
    """关掉可能遮挡筛选/字段的弹窗浮层(只点关闭类, 只读)"""
    try:
        await page.evaluate(r"""() => {
            for (const e of document.querySelectorAll('*')) {
                const t = (e.textContent || '').trim();
                if (e.children.length === 0 && (t === '我知道了' || t === '忽略')) { try { e.click(); } catch (x) {} }
            }
            for (const c of document.querySelectorAll('.next-icon-close_blod, .next-dialog-close')) {
                try { c.click(); } catch (x) {}
            }
        }""")
    except Exception:
        pass


async def _click_expand(page):
    """展开筛选区(店铺分类默认折叠在「展开」后). 返回是否点到。"""
    try:
        return bool(await page.evaluate(r"""() => {
            for (const e of document.querySelectorAll('button, span, a, div')) {
                const t = (e.textContent || '').trim();
                if (e.children.length === 0 && t === '展开' && e.getBoundingClientRect().width > 0) { e.click(); return true; }
            }
            return false;
        }"""))
    except Exception:
        return False


async def probe_list(page):
    """列表页: dump「店铺分类」标签/select, 点开下拉 dump 选项文本与元素选择器。只读不改筛选。"""
    await page.goto(SOLD_OUT_URL, wait_until='domcontentloaded', timeout=40000)
    await asyncio.sleep(10)
    await close_overlays(page)
    await asyncio.sleep(1)

    info = await page.evaluate(JS_LIST_SCAN)
    info['filter_expanded'] = False
    if not info.get('shopcat_candidate'):
        if await _click_expand(page):
            info['filter_expanded'] = True
            await asyncio.sleep(3)
            await close_overlays(page)
            info = await page.evaluate(JS_LIST_SCAN)
            info['filter_expanded'] = True

    cand = info.get('shopcat_candidate')
    info['dropdown_opened'] = False
    info['menu_containers'] = []
    info['options'] = []
    info['option_texts'] = []
    if cand:
        def _open_js():
            return r"""() => {
                const inp = document.getElementById('queryShopCategoryId');
                let sel = inp ? inp.closest('.next-select') : null;
                if (!sel) {
                    for (const lab of document.querySelectorAll('span,div,label')) {
                        const t = (lab.textContent || '').trim();
                        if (!(lab.children.length === 0 && t.length < 20 && t.indexOf('店铺分类') >= 0)) continue;
                        let c = lab;
                        for (let i = 0; i < 12 && c; i++) {
                            const s = c.querySelectorAll('.next-select');
                            if (s.length) { sel = s[0]; break; }
                            c = c.parentElement;
                        }
                        if (sel) break;
                    }
                }
                if (!sel) return false;
                sel.scrollIntoView({block: 'center'});
                const trg = sel.querySelector('.next-select-trigger') || sel;
                trg.click();
                return true;
            }"""
        opened = False
        try:
            await page.evaluate(_open_js())
            await asyncio.sleep(2.5)
            opened = bool(await page.evaluate(
                "() => [...document.querySelectorAll('.next-overlay-inner.next-select-popup-wrap,.next-tree-select,.next-menu')]"
                ".some(e => e.getBoundingClientRect().width > 0)"))
        except Exception as e:
            log(f"  · 点开下拉(JS)异常: {str(e)[:60]}")
        if not opened and cand.get('x') and cand.get('y'):
            try:
                await page.mouse.click(cand['x'], cand['y'])
                await asyncio.sleep(2.5)
                opened = bool(await page.evaluate(
                    "() => [...document.querySelectorAll('.next-overlay-inner.next-select-popup-wrap,.next-tree-select,.next-menu')]"
                    ".some(e => e.getBoundingClientRect().width > 0)"))
            except Exception as e:
                log(f"  · 点开下拉(鼠标)异常: {str(e)[:60]}")
        opts = await page.evaluate(JS_DUMP_OPTIONS)
        info['dropdown_opened'] = bool(opts.get('opened_menu'))
        info['menu_containers'] = opts.get('menu_containers', [])
        info['options'] = opts.get('options', [])
        info['option_texts'] = opts.get('option_texts', [])
        # 关闭下拉, 保持筛选条件不变
        try:
            await page.keyboard.press('Escape')
            await asyncio.sleep(0.5)
        except Exception:
            pass
    return info


async def probe_edit(page, item_id):
    """编辑页: dump 主标题/品牌/导购标题容器 + AI 元素 + 长度上限。只读不提交。"""
    await page.goto(EDIT_URL.format(id=item_id), wait_until='domcontentloaded', timeout=60000)
    for _ in range(18):   # 等表单水合, 最多 ~36s
        await asyncio.sleep(2)
        try:
            if await page.evaluate("() => !!document.querySelector('#sell-field-title')"):
                break
        except Exception:
            pass
    await asyncio.sleep(3)
    await close_overlays(page)
    await asyncio.sleep(1)
    info = await page.evaluate(JS_EDIT_SCAN)
    info['item_id'] = str(item_id)
    return info


def parse_args(argv):
    """-> (do_list, item_ids)"""
    do_list = '--list' in argv
    item_ids = []
    for i, a in enumerate(argv):
        if a == '--item' and i + 1 < len(argv):
            item_ids.append(argv[i + 1])
    if not do_list and not item_ids:
        do_list = True   # 无参默认探列表
    return do_list, item_ids


async def main():
    do_list, item_ids = parse_args(sys.argv[1:])
    b, ctx = await connect_cdp(CDP_PORT,
                               keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    page = await ctx.new_page()
    out = {'ts': time.strftime('%Y-%m-%d %H:%M:%S')}
    try:
        if do_list:
            log("=== 探列表页「店铺分类」筛选 ===")
            out['list'] = await probe_list(page)
            c = out['list'].get('shopcat_candidate') or {}
            log(f"list: 候选 input={c.get('input_id')} 展开={out['list'].get('filter_expanded')} "
                f"开下拉={out['list'].get('dropdown_opened')} 选项={out['list'].get('option_texts')}")
        out['edit'] = {}
        for iid in item_ids:
            log(f"=== 探编辑页 item {iid} ===")
            out['edit'][iid] = await probe_edit(page, iid)
            e = out['edit'][iid]
            log(f"edit[{iid}]: title={bool(e.get('title_container'))} brand_id={(e.get('brand_container') or {}).get('id')} "
                f"shopping={e.get('shopping_wrapper_present')} ai_icons="
                f"{[(a.get('nearest_id_ancestor'), a.get('cls')) for a in e.get('ai_icons', [])]} "
                f"counters={[c['text'] for c in e.get('counters', [])]}")
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        log(f"dump -> {OUT}")
    finally:
        try:
            await page.close()
        except Exception:
            pass
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
