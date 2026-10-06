# 淘宝「睡衣/家居服」改品牌 + AI 导购标题 + AI 新主标题 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把淘宝默认店「睡衣/家居服」店铺分类下的在售+仓库商品，品牌统一为「瑰若」，用平台 AI 生成导购标题和新主标题（新主标题必须以「瑰若」开头），并提交生效。

**Architecture:** 新建独立脚本 `edit_brand_title_batch.py`，骨架复用 `assign_shop_category_v2.py`（编辑页水合/清浮层/保持上架状态/提交/进度/风控 exit42），字段填充复用归档 `edit_jeans_batch.py`（品牌 React fiber 选择、导购标题 `.ai-icon` 的 AI 采纳），主标题 AI 用「在标题字段容器内按 `.ai-icon`/文本匹配 AI 触发 → 采纳按钮」的通用定位；纯逻辑抽到 `brand_title_rules.py` 做单测。商品清单用列表页「店铺分类」筛选采集。

**Tech Stack:** Python 3.9 `automation/venv/bin/python`、Playwright async、Chrome CDP 9222（窗口模式）、淘宝卖家后台 + `item.upload.taobao.com` 编辑页。

## Global Constraints

- 平台：**淘宝默认店**（shop_id=1），CDP 端口 **9222**；提交类必须**窗口模式** Chrome（headless 会被 RGV587 拦）。
- 解释器固定：`/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python`（禁止 `python3` 裸跑）。
- 品牌固定 **瑰若**；新主标题**前两个字必须是「瑰若」**；标题上限暂按 **30 汉字**（Phase 0 探路确认真实上限，若不同改 `TITLE_MAX`）。
- 执行顺序固定：**品牌 → 导购标题 AI → 新主标题 AI → 提交**（用户明确要求不改序）。
- 失败策略：品牌选不到 / 导购标题 AI 失败 / 主标题 AI 失败 / 提交失败 → **整件标 `failed` 且不提交**，由 `--retry-failed` 收敛；数据问题转 `skipped` 不自动重试。
- 不改价格、不改店铺分类、不改 SKU/图片；提交时**维持原上/下架状态**（在售保持立刻上架、仓库保持放入仓库）。
- **不做回滚工具**（用户确认不需要）。
- 路径常量用 **spzx 内绝对路径**（`automation/sourcing/...`），不得出现旧路径 `/Users/qyk9527/sourcing`。
- 运行期产物（`brand_title_targets.jsonl`、`brand_title_progress.json`、探路 dump）必须被 `.gitignore` 覆盖，不得 `git add -A`。
- **git commit 步需用户明确授权**；未授权时把 commit 步当检查点，跑完验证后停下等确认（仓库全局规则：未经要求不提交）。

---

### Task 1: 纯逻辑模块 `brand_title_rules.py` + 单测

**Files:**
- Create: `automation/sourcing/brand_title_rules.py`
- Create: `automation/sourcing/test_brand_title_rules.py`

**Interfaces:**
- Produces:
  - `ensure_guiruo_prefix(title: str, prefix: str = '瑰若', max_len: int = 30) -> str`
  - `dedup_targets(rows: list[dict]) -> list[dict]`；每行 `{itemId:str, title:str, pool:'onsale'|'warehouse'}`
  - `merge_progress(disk: dict, prog: dict) -> dict`；键 `done:list[str]`, `skipped:list[str]`, `failed:dict[str,dict]`

- [ ] **Step 1: Write the failing test**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brand_title_rules 自检. 直跑: venv/bin/python test_brand_title_rules.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brand_title_rules import ensure_guiruo_prefix, dedup_targets, merge_progress


def test_prefix_added_when_missing():
    assert ensure_guiruo_prefix('性感蕾丝睡裙女') == '瑰若性感蕾丝睡裙女'


def test_prefix_not_duplicated():
    assert ensure_guiruo_prefix('瑰若性感蕾丝睡裙女') == '瑰若性感蕾丝睡裙女'


def test_prefix_stripped_when_in_middle():
    # 旧标题品牌词不在开头: 去重后前置, 不出现两次
    out = ensure_guiruo_prefix('性感瑰若蕾丝睡裙')
    assert out.startswith('瑰若') and out.count('瑰若') == 1


def test_prefix_empty_title():
    assert ensure_guiruo_prefix('') == '瑰若'


def test_prefix_truncates_to_max():
    out = ensure_guiruo_prefix('甲' * 100, max_len=30)
    assert len(out) == 30 and out.startswith('瑰若')


def test_dedup_onsale_wins():
    rows = [
        {'itemId': '1', 'title': 'a', 'pool': 'warehouse'},
        {'itemId': '1', 'title': 'b', 'pool': 'onsale'},
        {'itemId': '2', 'title': 'c', 'pool': 'warehouse'},
    ]
    out = {r['itemId']: r for r in dedup_targets(rows)}
    assert len(out) == 2
    assert out['1']['pool'] == 'onsale' and out['1']['title'] == 'b'


def test_merge_progress_failed_pruned_by_done():
    disk = {'done': ['1'], 'skipped': [], 'failed': {'1': {'error': 'x'}, '2': {'error': 'y'}}}
    prog = {'done': ['3'], 'skipped': ['2'], 'failed': {'3': {'error': 'z'}}}
    m = merge_progress(disk, prog)
    assert set(m['done']) == {'1', '3'}
    assert set(m['skipped']) == {'2'}
    assert list(m['failed'].keys()) == []  # 1 done / 2 skipped 被剔除, 3 也 done


if __name__ == '__main__':
    test_prefix_added_when_missing()
    test_prefix_not_duplicated()
    test_prefix_stripped_when_in_middle()
    test_prefix_empty_title()
    test_prefix_truncates_to_max()
    test_dedup_onsale_wins()
    test_merge_progress_failed_pruned_by_done()
    print('PASS: brand_title_rules')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `automation/venv/bin/python automation/sourcing/test_brand_title_rules.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'brand_title_rules'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""淘宝品牌/标题批处理的纯逻辑: 瑰若前缀规整、目标去重、进度合并。
浏览器无关, 单测直跑。"""
PREFIX = '瑰若'
TITLE_MAX = 30  # Phase 0 探路确认淘宝标题真实上限, 不符则改这里


def ensure_guiruo_prefix(title, prefix=PREFIX, max_len=TITLE_MAX):
    """保证标题前两个字是 prefix: 去掉标题里所有 prefix 后前置一个, 再按 max_len 截断。"""
    t = (title or '').strip()
    t = t.replace(prefix, '')
    out = prefix + t
    return out[:max_len]


def dedup_targets(rows):
    """按 itemId 去重; 同一 itemId 同时出现在两池时 onsale 优先。"""
    seen = {}
    for r in rows:
        iid = str(r.get('itemId') or '')
        if not iid:
            continue
        cur = seen.get(iid)
        pool = r.get('pool', 'warehouse')
        if cur is None or (pool == 'onsale' and cur.get('pool') != 'onsale'):
            seen[iid] = {'itemId': iid, 'title': r.get('title', ''), 'pool': pool}
    return list(seen.values())


def merge_progress(disk, prog):
    """磁盘合并: done/skipped 并集, failed 覆盖后剔除已 done/skipped(防旧档复活)。"""
    merged = {
        'done': sorted(set(disk.get('done', [])) | set(prog.get('done', []))),
        'skipped': sorted(set(disk.get('skipped', [])) | set(prog.get('skipped', []))),
        'failed': {**disk.get('failed', {}), **prog.get('failed', {})},
    }
    for k in list(merged['failed']):
        if k in merged['done'] or k in merged['skipped']:
            del merged['failed'][k]
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `automation/venv/bin/python automation/sourcing/test_brand_title_rules.py`
Expected: `PASS: brand_title_rules`

- [ ] **Step 5: Commit (需授权)**

```bash
git add automation/sourcing/brand_title_rules.py automation/sourcing/test_brand_title_rules.py
git commit -m "feat(sourcing): 瑰若标题前缀规整与目标去重纯逻辑 + 单测"
```

---

### Task 2: Phase 0 探路脚本（只读，dump 选择器）

**Files:**
- Create: `automation/sourcing/probe_brand_title_edit.py`
- Output（gitignore）: `automation/sourcing/probe_brand_title_out.json`

**Interfaces:**
- 独立运行，不改数据。dump 两类信息：列表页「店铺分类」筛选下拉 DOM；编辑页主标题/品牌/导购标题容器 + AI 触发元素。
- 产出供 Task 3/4 校准 `set_brand` / `ai_guide_title` / `ai_main_title` / `enumerate_targets` 的 selector。

- [ ] **Step 1: 写探路脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase 0 只读探路: dump 列表页「店铺分类」筛选 + 编辑页字段/AI 元素, 供校准 selector。
用法: venv/bin/python probe_brand_title_edit.py --list        # 只探列表页
      venv/bin/python probe_brand_title_edit.py --item <itemId>  # 探编辑页
输出: probe_brand_title_out.json"""
import asyncio
import json
import os
import sys
import time

from cdp_utils import connect_cdp

CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "probe_brand_title_out.json")
EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def probe_list(page):
    await page.goto("https://myseller.taobao.com/home.htm/SellManage/sold_out",
                    wait_until='domcontentloaded', timeout=40000)
    await asyncio.sleep(10)
    return await page.evaluate(r"""() => {
        const out = {labels: [], selects: []};
        for (const e of document.querySelectorAll('*')) {
            const t = (e.textContent||'').trim();
            if (e.children.length === 0 && /店铺分类|分类/.test(t) && t.length < 20) out.labels.push(t);
        }
        for (const s of document.querySelectorAll('.next-select, [class*=select]')) {
            const r = s.getBoundingClientRect();
            if (r.width > 20 && r.height > 10) {
                out.selects.push({cls: (s.className||'').toString().slice(0,120),
                                  id: s.id, text: (s.innerText||'').trim().slice(0,60)});
            }
        }
        return out;
    }""")


async def probe_edit(page, item_id):
    await page.goto(EDIT_URL.format(id=item_id), wait_until='domcontentloaded', timeout=60000)
    await asyncio.sleep(12)
    return await page.evaluate(r"""() => {
        const wrap = (sel) => { const e = document.querySelector(sel); if (!e) return null;
            return {id: e.id, cls: (e.className||'').toString().slice(0,120),
                    text: (e.innerText||'').trim().slice(0,200)}; };
        const ai = [];
        for (const e of document.querySelectorAll('[class*=ai], [class*=Ai], [class*=AI]')) {
            const r = e.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) ai.push({cls: (e.className||'').toString().slice(0,120),
                text: (e.innerText||'').trim().slice(0,30), title: e.getAttribute('title')||''});
        }
        const aiText = [];
        for (const e of document.querySelectorAll('button,span,div')) {
            const t = (e.innerText||'').trim();
            if (e.children.length === 0 && t.length < 12 && /AI|智能|生成|帮我/.test(t)) aiText.push(t);
        }
        return {title: wrap('#sell-field-title'), brand: wrap('[class*=wrapper]:has(*[data-...])'),
                shopping: wrap('#sell-field-shopping_title'), ai, aiText: [...new Set(aiText)]};
    }""")


async def main():
    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    page = await ctx.new_page()
    out = {}
    try:
        if '--list' in sys.argv or not any(a.startswith('--item') for a in sys.argv):
            out['list'] = await probe_list(page)
            log(f"list: {json.dumps(out['list'], ensure_ascii=False)[:600]}")
        if '--item' in sys.argv:
            iid = sys.argv[sys.argv.index('--item') + 1]
            out['edit'] = await probe_edit(page, iid)
            log(f"edit: {json.dumps(out['edit'], ensure_ascii=False)[:900]}")
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        log(f"dump -> {OUT}")
    finally:
        await page.close()
        await b.close()


if __name__ == '__main__':
    asyncio.run(main())
```

> 注：`brand` 的临时选择器故意留 `[class*=wrapper]` 占位，Step 3 会依据 dump 结果改成真实选择器（品牌字段容器形如 `.sell-component-info-wrapper-wrap`）。这是**探路脚本**，不是生产代码，允许先粗后精。

- [ ] **Step 2: 启动窗口模式 Chrome 9222 并确认登录**

Run（窗口模式，勿加 `--headless`）:
```bash
nohup arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 \
  --user-data-dir=/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile --no-first-run --disable-extensions \
  --disable-features=TranslateUI,site-per-process --disable-background-timers \
  --disable-backgrounding-occluded-windows --disable-background-networking \
  --renderer-process-limit=6 --js-flags="--max-old-space-size=512" \
  --window-position=-32000,-32000 --window-size=1400,900 "https://myseller.taobao.com/home.htm" &
open -na "Google Chrome"
```
Expected: `curl -s http://127.0.0.1:9222/json/version` 有返回；卖家后台已登录（未登录先人工扫码）。

- [ ] **Step 3: 跑探路并记录选择器**

Run:
```bash
automation/venv/bin/python automation/sourcing/probe_brand_title_edit.py --list
automation/venv/bin/python automation/sourcing/probe_brand_title_edit.py --item <一个睡衣itemId>
```
Expected: `probe_brand_title_out.json` 写出。人工核对并**回写本 spec §Phase 0** 与 `brand_title_rules.TITLE_MAX`：
1. 「店铺分类」下拉容器 selector + 选项真实文本（睡衣/家居服 还是 家居服/睡衣）
2. 主标题容器 `#sell-field-title` 是否存在；主标题 AI 触发元素（`.ai-icon`？按钮文本？）
3. 品牌字段容器 selector（用于 `set_brand`）
4. 主标题字段长度上限（页面计数器，如 `0/30`）

- [ ] **Step 4: Commit（需授权）**

```bash
git add automation/sourcing/probe_brand_title_edit.py
git commit -m "chore(sourcing): 品牌/标题批处理 Phase 0 探路脚本"
```

---

### Task 3: 编辑页字段函数（品牌 / 导购标题 AI / 主标题 AI）

**Files:**
- Create: `automation/sourcing/edit_brand_title_batch.py`（本 Task 先放字段函数与常量；Task 4 补主循环）
- Modify: `brand_title_rules.TITLE_MAX`（若探路发现上限不同）

**Interfaces:**
- Consumes: `brand_title_rules.ensure_guiruo_prefix`
- Produces（Task 4 依赖，签名固定）:
  - `async def set_brand(page, brand='瑰若') -> tuple[bool, str]`
  - `async def ai_guide_title(page) -> tuple[bool, str]`
  - `async def ai_main_title(page, prefix='瑰若') -> tuple[bool, str]`
  - `async def read_main_title(page) -> str`

- [ ] **Step 1: 写字段函数（含品牌 fiber 选择 / 导购 AI / 主标题 AI）**

```python
# --- edit_brand_title_batch.py 顶部 ---
import asyncio
import os
import random
import sys
import time
import traceback

from cdp_utils import connect_cdp
from brand_title_rules import ensure_guiruo_prefix, TITLE_MAX
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


async def _pick_option_with_scroll(page, value, tries=12):
    """在已展开的 next-select 虚拟列表里找 value: 找不到就滚动加载再找。品牌下拉虚拟化必需。"""
    for _ in range(tries):
        clicked = await page.evaluate(r"""(val) => {
            const els = [...document.querySelectorAll('.next-menu-item, .next-select-menu-item, li, .next-tree-node-label')];
            for (const e of els) {
                if (e.getBoundingClientRect().width > 0 && (e.innerText||'').trim() === val) { e.click(); return true; }
            }
            return false;
        }""", value)
        if clicked:
            return True
        await page.evaluate(r"""() => {
            const menu = document.querySelector('.next-select-menu, .next-overlay-inner.next-select-popup-wrap, .next-virtual-list');
            if (menu) menu.scrollTop = menu.scrollHeight;
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
    applied = False
    for _ in range(15):
        await asyncio.sleep(1)
        applied = await page.evaluate(r"""() => {
            const re = /立即使用|采纳|使用该标题|应用/;
            for (const e of document.querySelectorAll('.adopt-btn, button, span')) {
                if (e.getBoundingClientRect().width > 0 && re.test((e.textContent||'').trim())) { e.click(); return true; }
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
```

- [ ] **Step 2: 语法编译检查**

Run: `automation/venv/bin/python -m py_compile automation/sourcing/edit_brand_title_batch.py`
Expected: 无输出（exit 0）。

- [ ] **Step 3: 单件实跑（不进 Task 4 主循环前，先用临时片段或探路脚本调用）**

在窗口模式 Chrome 下，用一个真实睡衣 itemId 手工跑：
```bash
automation/venv/bin/python - <<'PY'
import asyncio, sys
sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
import edit_brand_title_batch as m
from cdp_utils import connect_cdp
async def main():
    b, ctx = await connect_cdp(m.CDP_PORT, keep_urls=["myseller.taobao.com","item.upload.taobao.com"], log=m.log)
    page = await ctx.new_page()
    await page.goto(m.EDIT_URL.format(id='<睡衣itemId>'), wait_until='domcontentloaded', timeout=60000)
    print('ready title:', await m.wait_edit_ready(page))
    print('brand:', await m.set_brand(page))
    print('guide:', await m.ai_guide_title(page))
    print('main :', await m.ai_main_title(page))
    await page.close(); await b.close()
asyncio.run(main())
PY
```
Expected: 三个都返回 True；编辑页上品牌显示瑰若、导购标题非空、主标题以瑰若开头。**这是 Task 3 的验收，也是主标题选择器的最终校准点**；若 `ai_main_title` 报「触发元素未找到」，回到 Task 2 dump 校准后修此函数。

- [ ] **Step 4: Commit（需授权）**

```bash
git add automation/sourcing/edit_brand_title_batch.py
git commit -m "feat(sourcing): 淘宝品牌/导购标题/主标题 AI 字段填充"
```

---

### Task 4: 清单采集 + `process_one` + 主循环 + 进度

**Files:**
- Modify: `automation/sourcing/edit_brand_title_batch.py`（追加枚举与主循环）

**Interfaces:**
- Consumes: Task 3 的 `set_brand/ai_guide_title/ai_main_title`；`assign_shop_category` 的 `wait_edit_ready/handle_recommend_dialog/scroll_edit_page/check_listing_mode/click_submit/cleanup_leaked_tabs`；`compliance_filler.clear_overlays`；`brand_title_rules.dedup_targets/merge_progress`
- Produces:
  - `async def enumerate_targets(ctx, cat_text) -> list[dict]`
  - `async def process_one(ctx, rec) -> tuple[str, str]`（status: ok/fail/risk/skip）
  - `def load_progress() -> dict` / `def save_progress(prog) -> None`（fcntl 锁+`merge_progress`）
  - CLI: `--enumerate --test --limit N --start N --retry-failed --ids`

- [ ] **Step 1: 写清单采集 `enumerate_targets`**

```python
TARGETS_FILE = os.path.join(BASE, "brand_title_targets.jsonl")
PROGRESS_FILE = os.path.join(BASE, "brand_title_progress.json")
LIST_URLS = {
    'sold_out': "https://myseller.taobao.com/home.htm/SellManage/sold_out",
    'in_stock': "https://myseller.taobao.com/home.htm/SellManage/in_stock",
}


async def _apply_shop_cat_filter(page, cat_text):
    """「店铺分类」筛选: 先点「展开」, 再开 input#queryShopCategoryId 的 next-select, 选 cat_text(tree-select)。
    返回 (ok,msg)。选择器来自 Phase 0 探路。"""
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
        const opts = [...document.querySelectorAll('.next-tree-node-label, .next-tree-node-label-selectable, .next-menu-item, li')];
        for (const o of opts) {
            if (o.getBoundingClientRect().width > 0 && (o.innerText||'').trim() === cat) { o.click(); return true; }
        }
        return false;
    }""", cat_text)
    await asyncio.sleep(1.5)
    return (True, 'filter set') if picked else (False, f'店铺分类选项未找到: {cat_text}')


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
            # 点搜索
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
    return dedup_targets(out)
```

- [ ] **Step 2: 写进度读写与 `build_todo`**

```python
import fcntl
import json


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
```

- [ ] **Step 3: 写 `process_one`**

```python
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
```

- [ ] **Step 4: 写 `main()`（CLI + 枚举模式 + 主循环 + 风控 exit42）**

```python
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
```

- [ ] **Step 5: 编译检查 + `--enumerate` 实跑**

Run:
```bash
automation/venv/bin/python -m py_compile automation/sourcing/edit_brand_title_batch.py
automation/venv/bin/python automation/sourcing/edit_brand_title_batch.py --enumerate
```
Expected: `brand_title_targets.jsonl` 生成且非空；`wc -l` 数量与列表页「睡衣/家居服」筛选后的件数吻合。若 `_apply_shop_cat_filter` 报「下拉未找到」→ 用 Task 2 dump 校准。

- [ ] **Step 6: `--test` 单件实跑**

Run: `automation/venv/bin/python automation/sourcing/edit_brand_title_batch.py --test`
Expected: 1 件返回 `✓`；卖家后台确认品牌=瑰若、导购标题非空、主标题以瑰若开头且状态未变。

- [ ] **Step 7: Commit（需授权）**

```bash
git add automation/sourcing/edit_brand_title_batch.py
git commit -m "feat(sourcing): 淘宝睡衣/家居服批量改品牌+AI导购标题+AI主标题主循环"
```

---

### Task 5: 冷却续跑包装 `run_brand_title.sh`

**Files:**
- Create: `automation/sourcing/run_brand_title.sh`

**Interfaces:**
- Consumes: `edit_brand_title_batch.py` 的 exit 42（风控）
- Produces: 循环续跑；非 42 退出即停止并打印日志

- [ ] **Step 1: 写包装脚本**

```bash
#!/bin/bash
# run_brand_title.sh — 品牌/标题批处理冷却续跑包装 (仅本脚本, 勿 kill python 后不杀它)
# 风控 exit 42 → 冷却阶梯 20m→40m→120m 封顶后续跑; 其他退出码停止。
cd "$(dirname "$0")" || exit 1
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
COOLDOWNS=(1200 2400 7200)
i=0
while true; do
  echo "[$(date '+%F %T')] 启动一轮: $PY edit_brand_title_batch.py $*"
  "$PY" edit_brand_title_batch.py "$@"
  code=$?
  if [ "$code" -ne 42 ]; then
    echo "[$(date '+%F %T')] 退出码 $code, 停止"
    exit "$code"
  fi
  secs=${COOLDOWNS[$i]:-${COOLDOWNS[2]}}
  [ "$i" -lt 2 ] && i=$((i+1))
  echo "[$(date '+%F %T')] 风控冷却 ${secs}s 后续跑"
  sleep "$secs"
done
```

- [ ] **Step 2: 语法检查**

Run: `bash -n automation/sourcing/run_brand_title.sh`
Expected: 无输出（exit 0）。

- [ ] **Step 3: 小批实跑（10 件）验证续跑与风控路径**

Run（窗口模式 Chrome 已开）:
```bash
nohup automation/sourcing/run_brand_title.sh --limit 10 > /tmp/brand_title_run.log 2>&1 &
```
Expected: 日志出现逐件 `✓`；若命中风控，进程退出码 42、包装打印冷却后自动重启；`brand_title_progress.json` 的 done 递增。抽查 3 件后台确认三项都生效。

- [ ] **Step 4: Commit（需授权）**

```bash
git add automation/sourcing/run_brand_title.sh
git commit -m "chore(sourcing): 品牌/标题批处理风控冷却续跑包装"
```

---

### Task 6: 文档 + .gitignore + 全量跑 runbook

**Files:**
- Modify: `automation/sourcing/AGENTS.md`（追加一节）
- Modify: `.gitignore`（确认覆盖运行期产物）
- Modify: `docs/superpowers/specs/2026-10-05-taobao-brand-title-ai-design.md`（回写 Phase 0 探路结论）

- [ ] **Step 1: 确认 gitignore 覆盖**

检查 `.gitignore` 是否已含 `automation/*/brand_title_out*`、`automation/*/probe_brand_title_out.json`；若无则追加：
```
automation/*/brand_title_targets.jsonl
automation/*/brand_title_progress.json*
automation/*/probe_brand_title_out.json
```
（`.jsonl` 已在既有规则内，凭据/产物不得提交。）

- [ ] **Step 2: 追加 AGENTS.md 坑位记录**

在 `automation/sourcing/AGENTS.md` 末尾追加：
```markdown
## 品牌/标题批处理 (edit_brand_title_batch.py, 2026-10-05)

淘宝默认店「睡衣/家居服」店铺分类商品: 品牌→瑰若 + 导购标题平台AI + 主标题平台AI(前缀必须瑰若)。
- 清单: 列表页「店铺分类」筛选(真实下拉文本见 spec Phase 0), 出售中+仓库中 → `brand_title_targets.jsonl`。
- 顺序固定 品牌 → 导购标题AI → 主标题AI; 任一步失败整件 failed 不提交。
- 导购标题 `.ai-icon` 抄归档 `edit_jeans_batch.fill_ai_guide_title`; 主标题 AI 选择器见探路 dump。
- 排序 onsale 优先; 风控 exit 42 → `run_brand_title.sh` 冷却阶梯续跑; 提交必须窗口模式 9222。
- 进度 `brand_title_progress.json`(done/failed/skipped); 纯逻辑单测 `test_brand_title_rules.py`。
```

- [ ] **Step 3: 回写 spec Phase 0 结论**

把 Task 2 探路得到的：店铺分类下拉文本/选择器、主标题 AI 触发元素、品牌字段容器、标题上限，写回 spec 的 Phase 0 小节与 `TITLE_MAX`。

- [ ] **Step 4: 全量 runbook（写入 spec 或 AGENTS 的“全量跑”段）**

```bash
# 0. 窗口模式 Chrome 9222 已登录 (见 Task 2 Step 2)
# 1. 重采清单(分类有变动时)
automation/venv/bin/python automation/sourcing/edit_brand_title_batch.py --enumerate
# 2. 全量续跑(风控自动冷却)
nohup automation/sourcing/run_brand_title.sh > /tmp/brand_title_run.log 2>&1 &
# 3. 监控
tail -f /tmp/brand_title_run.log
# 4. 收尾对账: 清单数 == done + failed + skipped
automation/venv/bin/python -c "
import json
t=sum(1 for _ in open('automation/sourcing/brand_title_targets.jsonl'))
p=json.load(open('automation/sourcing/brand_title_progress.json'))
print('targets',t,'done',len(p['done']),'failed',len(p['failed']),'skipped',len(p['skipped']))
"
# 5. 失败重试
automation/venv/bin/python automation/sourcing/edit_brand_title_batch.py --retry-failed
```

- [ ] **Step 5: Commit（需授权）**

```bash
git add .gitignore automation/sourcing/AGENTS.md docs/superpowers/specs/2026-10-05-taobao-brand-title-ai-design.md
git commit -m "docs(sourcing): 品牌/标题批处理 runbook、坑位与 Phase0 结论"
```

---

## Self-Review

**Spec coverage:**
- 圈选（店铺分类筛选、出售中+仓库）→ Task 4 Step 1（`enumerate_targets`/`_apply_shop_cat_filter`）。
- 单件流程 品牌→导购AI→主标题AI→提交 → Task 3 + Task 4 Step 3。
- 新主标题瑰若前缀 → Task 1 `ensure_guiruo_prefix` + Task 3 `ai_main_title` 强制前缀。
- 失败策略（AI失败不提交、转 failed/skip）→ Task 4 Step 3/4。
- 进度/风控 exit42/包装 → Task 4 Step 2/4 + Task 5。
- Phase 0 探路 → Task 2 + Task 6 Step 3 回写。
- 交付物（脚本/包装/AGENTS/产物 gitignore）→ Task 4/5/6。
- 非目标（不动价格/类目/回滚）→ 未生成相关任务，符合。

**Placeholder scan:** 探路脚本中 `brand` 临时选择器与主标题 AI 选择器是**有意的探路占位**，Task 3 Step 3 / Task 6 Step 3 明确要求校准回写；生产字段函数均给出完整可运行代码，无 TBD/TODO。

**Type consistency:** `set_brand/ai_guide_title/ai_main_title` 均返回 `(bool, str)`；`process_one` 返回 `(status, msg)`，status ∈ {ok,fail,risk,skip}；`build_todo`/`merge_progress`/`ensure_guiruo_prefix`/`dedup_targets` 名字在 Task 1、4 一致；`TARGETS_FILE/PROGRESS_FILE/EDIT_URL/BRAND/BRAND_LABEL/GUIDE_SEL` 常量一致。

**已知风险（执行时注意）：**
- 主标题 AI 可能不存在/不可用 → Task 3 Step 3 若校准失败，**停止并回报用户**，不擅自改成规则重写。
- 2000+ 件逐件 AI+提交会持续撞风控，必须窗口模式 + 冷却续跑；预计多轮。
- 编辑已提交过的商品会再次触发审核，属预期。
