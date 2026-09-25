# 淘宝归类 v2 合规填充器实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v2 提交前自动填齐淘宝 2026-09 新增的按类目必填字段（SKU 级+属性级），修复浮层拦截与「提取方式」勾选失效，PIC_STEAL-only 失败转 skipped。

**Architecture:** 新模块 `compliance_filler.py`（overlay 清理 / 提取方式真点击 / 错误态检测 / 按规则填充），v2 `process_one` 在调价前清浮层、提交前检测-填充-复检；主循环把仅剩盗图的失败转 skipped。选择器集中为模块级常量，Task 1 结构发现若与假设不符只改常量不改逻辑。

**Tech Stack:** Python 3.9（`automation/venv/bin/python`）+ Playwright async + CDP 9222 窗口模式 Chrome。无 pytest——纯 assert 自检直跑。Fusion next-* 组件范式（本表单已证实的组件族）。

**Spec:** `docs/superpowers/specs/2026-09-25-shop-cat-compliance-filler-design.md`（commit 4d8c6ca）

## Global Constraints

- venv 统一 `automation/venv/bin/python`（3.9.6 兼容）；无 pytest，自检脚本纯 assert 直跑
- 默认值（写入真实在售商品，spec 钦定）：厚薄=常规；是否加绒=标题含「加绒/绒」→是否则否；款式=面板第一项；面料材质成分=聚酯纤维 100%；上市年份季节=按当天日期（如 2026年秋季）；是否商场同款=否；功能/适用场景=标题关键词推导否则默认第一项
- 不换主图；不自动创建运费模板；美甲池 skipped 不动；不改八类目规则与调价规则
- Chrome 红线：9222 已在线（当前空闲，v2 运行已停）；不 kill/重启 Chrome；不碰日常 Chrome；**探测/交互只开自己的 tab 用完即关**；出验证码/滑块立即停报 BLOCKED
- 进度文件 `shop_cat_v2_progress.json` 结构不变（done/failed/skipped 语义沿用，skipped 为 list 需去重追加）
- 工作目录 `automation/sourcing/`；git 只 add 任务列出的文件（工作区有用户未提交的 Java/AGENTS.md 改动，勿动勿提交）

---

### Task 1: UI 结构发现（只读 dump）

**Files:**
- Create: `automation/sourcing/probe_compliance_ui.py`
- Create: `automation/sourcing/compliance_ui_notes.md`

**Interfaces:**
- Produces: `compliance_ui_notes.md` 记录四类控件的真实 DOM 结构（选择器、组件类型、选项来源），Task 2-4 的实现依据；若与下述假设不符，**在 notes 中记录实际结构并给出选择器修正**（Task 2-4 实现者按 notes 调整 SELECTORS 常量，接口不变）
- 样本（已 failed 商品，只读不提交）：家居服 `1072552474230`、长裤 `1058428800598`、连衣裙 `888970440898`、秋冬款 `1071720043442`、other `1078910949614`

- [ ] **Step 1: 写 dump 脚本**

`probe_compliance_ui.py`（复用 cdp_utils/wait_edit_ready/scroll_edit_page/ensure_guard_tab 模式）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读 dump 合规相关控件结构 -> compliance_ui_notes.md. 绝不提交."""
import asyncio
import sys
import time
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page
from compliance_filler import clear_overlays

EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


DUMP_JS = r'''() => {
    const out = {};
    // A) SKU「去填写」按钮上下文
    const w = document.getElementById('sell-field-sku');
    if (w) {
        const btn = [...w.querySelectorAll('button, a, span, td')].find(e => (e.textContent||'').trim() === '去填写');
        out.qtf = btn ? {tag: btn.tagName, cls: String(btn.className).slice(0,80),
                         inZone: !!btn.closest('#sell-field-sku')} : null;
    }
    // B) 属性区: 面料/材质成分控件
    const matBtn = [...document.querySelectorAll('button, a, span, div')]
        .find(e => e.children.length === 0 && (e.textContent||'').trim() === '添加材质成分');
    out.matBtn = matBtn ? {tag: matBtn.tagName, cls: String(matBtn.className).slice(0,80)} : null;
    // C) 属性区各 select/radio 控件: label -> 组件类型
    out.attrs = [];
    for (const it of document.querySelectorAll('.next-form-item')) {
        const label = it.querySelector('.next-form-item-label');
        const lt = label ? label.textContent.trim().replace(/\*/g,'').trim() : '';
        if (!lt || lt.length > 10) continue;
        const comp = it.querySelector('.next-select, .next-radio-group, .next-checkbox-wrapper, .next-cascader, .next-input, textarea, [class*="material"]');
        out.attrs.push({label: lt, req: it.classList.contains('required'),
                        comp: comp ? (comp.className||'').toString().split(' ').slice(0,3).join(' ') : 'NONE'});
    }
    return out;
}'''


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    lines = ["# 合规控件结构发现 (自动生成 %s)\n" % time.strftime('%Y-%m-%d %H:%M')]
    try:
        for iid in sys.argv[1:]:
            if not iid.isdigit():
                continue
            page = await ctx.new_page()
            try:
                await page.goto(EDIT_URL.format(id=iid), timeout=60000, wait_until='domcontentloaded')
                title = await wait_edit_ready(page, timeout=40)
                if not title:
                    log(f"{iid} LOAD_FAIL"); continue
                await scroll_edit_page(page)
                await asyncio.sleep(1.5)
                await clear_overlays(page)
                info = await page.evaluate(DUMP_JS)
                lines.append(f"## {iid}\n```json\n{json.dumps(info, ensure_ascii=False, indent=1)}\n```\n")
                log(f"{iid}: qtf={bool(info.get('qtf'))} matBtn={bool(info.get('matBtn'))} attrs={len(info.get('attrs', []))}")
            except Exception as e:
                log(f"{iid} ERR {str(e)[:60]}")
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                await asyncio.sleep(2)
    finally:
        from assign_shop_category_v2 import ensure_guard_tab
        ensure_guard_tab()
        await b.close()
    with open('compliance_ui_notes.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    log("-> compliance_ui_notes.md")


import json
asyncio.run(main())
```

- [ ] **Step 2: 实施前先建空壳模块（供 import）**

创建 `compliance_filler.py`，只含 `clear_overlays`（本任务唯一被 import 的函数）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合规填充器: 淘宝 2026-09 新必填字段自动填充. spec: docs/superpowers/specs/2026-09-25-shop-cat-compliance-filler-design.md"""
import asyncio

OVERLAY_SELECTORS = (
    '.sku-preview-drag-wrapper',   # SKU 预览浮窗(内嵌 iframe, 拦截页面点击)
    '#struct-error-board',         # 优化建议错误面板
)


async def clear_overlays(page):
    """隐藏新增浮层(预览iframe/错误面板). 纯预览/诊断UI, 不含表单数据, 隐藏安全."""
    await page.evaluate("""(sels) => {
        for (const s of sels) {
            for (const e of document.querySelectorAll(s)) { e.style.display = 'none'; }
        }
    }""", list(OVERLAY_SELECTORS))
    await asyncio.sleep(0.3)
```

- [ ] **Step 3: 跑发现脚本（5 个样本）**

Run: `../venv/bin/python probe_compliance_ui.py 1072552474230 1058428800598 888970440898 1071720043442 1078910949614`
Expected: 5 个样本各产出 JSON dump；`compliance_ui_notes.md` 生成。

- [ ] **Step 4: 人工核对 notes 并补记结论**

阅读 `compliance_ui_notes.md`，在文件末尾追加一节「结论与选择器修正」：
1. 「去填写」的可点击元素选择器是什么（tag/class）
2. 「添加材质成分」按钮选择器
3. 属性区各目标字段（上市年份季节/是否商场同款/功能/适用场景）分别是什么组件（select/radio/多选）
4. 与 Task 2-4 代码中 SELECTORS 假设的差异清单（若无差异写「无」）

- [ ] **Step 5: Commit**

```bash
git add automation/sourcing/probe_compliance_ui.py automation/sourcing/compliance_filler.py automation/sourcing/compliance_ui_notes.md
git commit -m "feat(sourcing): 合规填充器起步-overlay清理+UI结构发现"
```

---

### Task 2: detect_gaps 错误态解析（纯函数）+ fill_extract_way

**Files:**
- Modify: `automation/sourcing/compliance_filler.py`
- Create: `automation/sourcing/test_compliance_filler.py`

**Interfaces:**
- Consumes: Task 1 的 `clear_overlays(page)`、notes 里的提取方式组件结论
- Produces: `KNOWN_FIELDS = ('厚薄','是否加绒','款式','面料','材质成分','上市年份季节','是否商场同款','功能','适用场景','提取方式')`；`parse_gaps(body_text) -> list[dict]`（纯函数，`{'name': str, 'zone': 'sku'|'prop'|'extract'}`）；`detect_gaps(page) -> list[dict]`（evaluate 读 body.innerText 后走 parse_gaps）；`fill_extract_way(page) -> (ok, msg)`；`is_image_only_failure(msg) -> bool`（纯函数）

- [ ] **Step 1: 写自检脚本（先失败）**

`test_compliance_filler.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compliance_filler 纯逻辑自检. 直跑: venv/bin/python test_compliance_filler.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compliance_filler import parse_gaps, is_image_only_failure

BODY = """
基础信息
1
商品属性
必填项未填
销售信息
3
销售规格
必填项未填
物流服务
1
提取方式
必填项未填
面料
必填项面料不能为空
厚薄不能为空
白色 - M：厚薄不能为空。
功能
必填项功能不能为空
是否商场同款
必填项是否商场同款不能为空
"""


def test_parse_gaps_known_fields():
    gaps = parse_gaps(BODY)
    names = {g['name'] for g in gaps}
    assert '厚薄' in names and '面料' in names and '提取方式' in names
    assert '功能' in names and '是否商场同款' in names
    zones = {g['name']: g['zone'] for g in gaps}
    assert zones['厚薄'] == 'sku'
    assert zones['提取方式'] == 'extract'
    assert zones['面料'] == 'prop'


def test_parse_gaps_no_false_positive():
    assert parse_gaps('全部字段已填写完成，厚薄=常规') == []
    assert parse_gaps('') == []


def test_image_only():
    assert is_image_only_failure('提交失败: 数据问题: ...CHK_IMAGE_PC_PIC_STEAL...mainImagesGroup...')
    assert not is_image_only_failure('CHK_IMAGE_PC_PIC_STEAL 销售规格 必填项未填')
    assert not is_image_only_failure('提交失败: 数据问题: 商品发布 错误(4) 销售规格 必填项未填')


if __name__ == '__main__':
    test_parse_gaps_known_fields()
    test_parse_gaps_no_false_positive()
    test_image_only()
    print('PASS: compliance filler pure logic')
```

- [ ] **Step 2: 跑自检确认失败**

Run: `../venv/bin/python test_compliance_filler.py`
Expected: `ImportError: cannot import name 'parse_gaps'`

- [ ] **Step 3: 实现**

`compliance_filler.py` 追加（Task 2-4 所有选择器常量集中在此，按 Task 1 notes 修正）：

```python
SKU_FIELDS = ('厚薄', '是否加绒', '款式')          # SKU 级(每行)字段
ZONE_EXTRACT, ZONE_SKU, ZONE_PROP = 'extract', 'sku', 'prop'
FIELD_ZONE = {'厚薄': ZONE_SKU, '是否加绒': ZONE_SKU, '款式': ZONE_SKU,
              '面料': ZONE_PROP, '材质成分': ZONE_PROP, '上市年份季节': ZONE_PROP,
              '是否商场同款': ZONE_PROP, '功能': ZONE_PROP, '适用场景': ZONE_PROP,
              '提取方式': ZONE_EXTRACT}
IMAGE_FAIL_MARK = 'PIC_STEAL'
FILL_FAIL_MARKS = ('必填', '不能为空', '规格')


def parse_gaps(body_text):
    """body 错误态文本 -> 已知字段缺失列表(去重保序). 纯函数."""
    gaps, seen = [], set()
    for name in FIELD_ZONE:
        hit = False
        for line in body_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if (name in line and ('不能为空' in line or '必填' in line)) or \
               (line == '必填项未填' and _prev_label_is(body_text, name)):
                hit = True
                break
        if hit and name not in seen:
            seen.add(name)
            gaps.append({'name': name, 'zone': FIELD_ZONE[name]})
    return gaps


def _prev_label_is(text, name):
    """面板形态: 字段名行后跟'必填项未填'行. 检查 name 行后 3 行内是否出现."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, l in enumerate(lines):
        if l == name or l.endswith(name):
            for nxt in lines[i + 1:i + 4]:
                if nxt == '必填项未填':
                    return True
    return False


def is_image_only_failure(msg):
    """提交失败信息是否仅剩图片(盗图)问题(无必填/规格类错误). 纯函数."""
    if IMAGE_FAIL_MARK not in msg:
        return False
    return not any(m in msg for m in FILL_FAIL_MARKS)


async def detect_gaps(page):
    """读页面错误态(自带上次失败态, 零试提交) -> parse_gaps."""
    body = await page.evaluate("() => document.body.innerText")
    return parse_gaps(body)


async def fill_extract_way(page):
    """提取方式: 浮层清理后 Playwright 真点「使用物流配送」label, 以 input.checked 翻转为准."""
    lbl = page.locator('#sell-field-tbExtractWay label', has_text='使用物流配送').first
    if await lbl.count() == 0:
        return False, 'NO_LABEL'
    await lbl.click(timeout=8000)
    await asyncio.sleep(0.8)
    checked = await page.evaluate("""() => {
        const el = document.querySelector('#sell-field-tbExtractWay');
        if (!el) return null;
        for (const l of el.querySelectorAll('label')) {
            if (/使用物流配送/.test(l.textContent||'')) {
                const i = l.querySelector('input');
                return i ? i.checked : null;
            }
        }
        return null;
    }""")
    if checked:
        return True, 'CHECKED'
    return False, 'CLICK_NO_EFFECT'
```

- [ ] **Step 4: 跑自检确认通过 + 真实验证**

Run: `../venv/bin/python test_compliance_filler.py`
Expected: `PASS: compliance filler pure logic`

真实验证（9222 在线，空闲时段）：对一个样本页跑「clear_overlays → fill_extract_way → 读 checked」：

```bash
../venv/bin/python - << 'EOF'
import asyncio
from cdp_utils import connect_cdp
from assign_shop_category import wait_edit_ready, scroll_edit_page
from compliance_filler import clear_overlays, fill_extract_way, detect_gaps

async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com","item.upload.taobao.com"], log=print)
    page = await ctx.new_page()
    await page.goto("https://item.upload.taobao.com/sell/v2/publish.htm?itemId=1072552474230&fromAIPublish=true",
                    timeout=60000, wait_until='domcontentloaded')
    await wait_edit_ready(page, timeout=40)
    await scroll_edit_page(page)
    await asyncio.sleep(1)
    await clear_overlays(page)
    print("gaps:", await detect_gaps(page))
    print("extract:", await fill_extract_way(page))
    await page.close()
    from assign_shop_category_v2 import ensure_guard_tab
    ensure_guard_tab()
    await b.close()

asyncio.run(main())
EOF
```
Expected: gaps 含 厚薄/面料/提取方式；extract=`('True','CHECKED')`。

- [ ] **Step 5: Commit**

```bash
git add automation/sourcing/compliance_filler.py automation/sourcing/test_compliance_filler.py
git commit -m "feat(sourcing): 合规填充器-错误态解析/提取方式真点击/盗图失败判定"
```

---

### Task 3: SKU 级填充（厚薄/是否加绒/款式，经「去填写」批量面板）

**Files:**
- Modify: `automation/sourcing/compliance_filler.py`
- Modify: `automation/sourcing/test_compliance_filler.py`

**Interfaces:**
- Consumes: Task 1 notes 的「去填写」面板结构、Task 2 的 `detect_gaps`/`ZONE_SKU`
- Produces: `sku_value_for(field, title) -> str`（纯函数：是否加绒标题派生，其余常量/第一项）；`fill_sku_gaps(page, gaps, title) -> (ok, msg)`（点「去填写」→面板逐行/批量设值→确认；面板确认按钮选择器按 notes）；填充后 re-detect 由调用方负责

- [ ] **Step 1: 写取值纯函数自检（先失败）**

`test_compliance_filler.py` 追加：

```python
def test_sku_value_for():
    from compliance_filler import sku_value_for
    assert sku_value_for('是否加绒', '冬季加绒加厚卫裤') == '是'
    assert sku_value_for('是否加绒', '夏季薄款牛仔裤') == '否'
    assert sku_value_for('厚薄', '任意标题') == '常规'
    assert sku_value_for('款式', '任意标题') is not None   # 面板第一项, 运行时取
```

Run: `../venv/bin/python test_compliance_filler.py`
Expected: FAIL (`ImportError: cannot import name 'sku_value_for'`)

- [ ] **Step 2: 实现取值函数 + 面板填充**

`compliance_filler.py` 追加（面板内部结构以 Task 1 notes 为准，以下为 Fusion 范式的基准实现，选择器不符时按 notes 修正 `SKU_PANEL` 常量组）：

```python
SKU_DEFAULTS = {'厚薄': '常规', '是否加绒': '否'}
JIA_RONG_KW = ('加绒', '绒')


def sku_value_for(field, title, options=None):
    """SKU 属性取值. options: 面板内可选项(款式等无默认值字段取第一项)."""
    if field == '是否加绒':
        return '是' if any(k in (title or '') for k in JIA_RONG_KW) else '否'
    if field in SKU_DEFAULTS:
        v = SKU_DEFAULTS[field]
        if options:
            for o in options:
                if o == v:
                    return v
            return options[0]
        return v
    return (options or [''])[0] if options else ''


# 去填写面板: 打开/行填充/确认 (结构以 compliance_ui_notes.md 为准)
SKU_PANEL = {
    'open': '#sell-field-sku td, #sell-field-sku button',   # 内含文本'去填写'的元素
    'row_select': '.next-dialog .next-select, [class*="batch"] .next-select',
    'option': '.next-menu-item',
    'confirm': '.next-dialog button:has-text("确定"), [class*="batch"] button:has-text("确定")',
}


async def fill_sku_gaps(page, gaps, title):
    """SKU 级缺失填充: 对每个字段走「去填写」批量面板."""
    import logging
    done = []
    for g in [g for g in gaps if g['zone'] == ZONE_SKU]:
        field = g['name']
        try:
            opener = page.locator('#sell-field-sku :text-is("去填写")').first
            if await opener.count() == 0:
                return False, f'{field}: 去填写入口未找到'
            await opener.click(timeout=8000)
            await asyncio.sleep(1.5)
            # 面板内的属性下拉: 第一个 next-select 即目标字段(面板只含该字段)
            sel = page.locator('.next-dialog .next-select, [class*="batch"] .next-select').first
            if await sel.count() == 0:
                return False, f'{field}: 面板未打开或无下拉'
            await sel.click(timeout=8000)
            await asyncio.sleep(1)
            options = await page.evaluate("""() =>
                [...document.querySelectorAll('.next-menu-item')]
                    .map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 20)""")
            value = sku_value_for(field, title, options)
            opt = page.locator('.next-menu-item', has_text=value).first
            if await opt.count() == 0:
                opt = page.locator('.next-menu-item').first
            await opt.click(timeout=8000)
            await asyncio.sleep(0.8)
            confirm = page.locator('.next-dialog button', has_text='确定').first
            if await confirm.count() > 0:
                await confirm.click(timeout=8000)
            await asyncio.sleep(1.5)
            done.append(f'{field}={value}')
        except Exception as e:
            return False, f'{field}: {str(e)[:60]}'
    return True, 'filled ' + ','.join(done)
```

- [ ] **Step 3: 自检通过 + 样本真实验证**

Run: `../venv/bin/python test_compliance_filler.py` → PASS（含新用例）。

真实验证（长裤样本，是否加绒）：页面打开 → `clear_overlays` → `fill_extract_way` → `fill_sku_gaps(page, [{'name':'是否加绒','zone':'sku'}], title)` → `detect_gaps` 确认「是否加绒」消失（写一次性 heredoc 脚本，模式同 Task 2 Step 4；不再提交）。
Expected: 返回 `filled 是否加绒=否`（标题不含加绒词）且 re-detect 无该字段。

- [ ] **Step 4: Commit**

```bash
git add automation/sourcing/compliance_filler.py automation/sourcing/test_compliance_filler.py
git commit -m "feat(sourcing): SKU级合规字段批量填充(去填写面板)"
```

---

### Task 4: 属性级填充（面料/上市年份季节/是否商场同款/功能/适用场景）

**Files:**
- Modify: `automation/sourcing/compliance_filler.py`
- Modify: `automation/sourcing/test_compliance_filler.py`

**Interfaces:**
- Consumes: Task 1 notes 的属性区控件结构、Task 2 `ZONE_PROP`
- Produces: `season_value() -> str`（纯函数：按当天日期）；`prop_value_for(field, title) -> list[str]`（纯函数：多选字段候选序列）；`fill_prop_gaps(page, gaps, title) -> (ok, msg)`（属性区逐字段填充：select 取值/多选勾选/材质成分组合）

- [ ] **Step 1: 写纯函数自检（先失败）**

`test_compliance_filler.py` 追加：

```python
def test_prop_values():
    from compliance_filler import prop_value_for, season_value
    s = season_value()
    assert '年' in s and '季' in s            # 如 2026年秋季
    assert prop_value_for('是否商场同款', 'x') == ['否']
    assert prop_value_for('面料', 'x') == ['聚酯纤维:100']
    assert prop_value_for('功能', '保暖加绒外套')[0] == '保暖'   # 标题关键词命中优先
    assert '居家' in prop_value_for('适用场景', '珊瑚绒睡衣家居服')
    assert prop_value_for('功能', '纯棉T恤')          # 推不出时仍有默认候选
```

Run: `../venv/bin/python test_compliance_filler.py` → Expected: FAIL

- [ ] **Step 2: 实现取值 + 属性区填充**

`compliance_filler.py` 追加（控件交互按 Task 1 notes 修正 `PROP_UI` 常量）：

```python
import datetime

PROP_KEYWORDS = {
    '功能': (('保暖', ('保暖', '加绒', '加厚', '毛绒', '羽绒')), ('其他', ())),
    '适用场景': (('居家', ('睡衣', '睡裙', '家居服', '居家')), ('日常', ())),
}
PROP_CONST = {'是否商场同款': ['否'], '面料': ['聚酯纤维:100']}


def season_value():
    d = datetime.date.today()
    m = d.month
    ji = '春' if m <= 3 else '夏' if m <= 6 else '秋' if m <= 9 else '冬'
    return f'{d.year}年{ji}季'


def prop_value_for(field, title):
    """返回候选值序列(依次尝试, 标题关键词命中优先). 面料特殊: '材质:含量' 列表."""
    if field in PROP_CONST:
        return PROP_CONST[field]
    if field == '上市年份季节':
        return [season_value()]
    cands = []
    for val, kws in PROP_KEYWORDS.get(field, ()):
        if any(k in (title or '') for k in kws):
            cands.append(val)
    if PROP_KEYWORDS.get(field):
        cands.append(PROP_KEYWORDS[field][-1][0])   # 默认兜底 = 最后一个候选
    return cands


async def _set_next_select(page, box, value):
    """在容器 box 内操作 .next-select: 展开->按文本选->校验."""
    sel = box.locator('.next-select').first
    await sel.click(timeout=8000)
    await asyncio.sleep(0.8)
    opt = page.locator('.next-menu-item', has_text=value).first
    if await opt.count() == 0:
        opt = page.locator('.next-menu-item').first
        value = (await opt.inner_text()).strip()
    await opt.click(timeout=8000)
    await asyncio.sleep(0.6)
    return value


async def fill_prop_gaps(page, gaps, title):
    """属性级缺失填充. 按字段名定位 .next-form-item(required) 容器."""
    done = []
    for g in [g for g in gaps if g['zone'] == ZONE_PROP]:
        field = g['name']
        try:
            if field in ('面料', '材质成分'):
                # 材质成分: 点「添加材质成分」-> 搜索材质 -> 勾选 -> 含量填 100
                add = page.locator('button:has-text("添加材质成分"), span:has-text("添加材质成分")').first
                await add.click(timeout=8000)
                await asyncio.sleep(1.2)
                search = page.locator('.next-dialog input, [class*="material"] input').first
                await search.fill('聚酯纤维')
                await asyncio.sleep(1)
                chk = page.locator('.next-dialog .next-menu-item, .next-dialog [class*="option"]', has_text='聚酯纤维').first
                await chk.click(timeout=8000)
                await asyncio.sleep(0.6)
                pct = page.locator('.next-dialog input[class*="input"]').nth(1)
                if await pct.count() > 0:
                    await pct.fill('100')
                confirm = page.locator('.next-dialog button', has_text='确定').first
                if await confirm.count() > 0:
                    await confirm.click(timeout=8000)
                done.append('面料=聚酯纤维100')
                continue
            box = page.locator('.next-form-item.required', has_text=field).first
            if await box.count() == 0:
                box = page.locator('.next-form-item', has_text=field).first
            if await box.count() == 0:
                return False, f'{field}: 表单项未找到'
            cands = prop_value_for(field, title)
            picked = None
            for v in cands:
                try:
                    picked = await _set_next_select(page, box, v)
                    break
                except Exception:
                    continue
            if not picked:
                return False, f'{field}: 候选值均未命中'
            done.append(f'{field}={picked}')
        except Exception as e:
            return False, f'{field}: {str(e)[:60]}'
    return True, 'filled ' + ','.join(done)
```

- [ ] **Step 3: 自检通过 + 样本真实验证**

Run: `../venv/bin/python test_compliance_filler.py` → PASS。

真实验证（连衣裙样本 888970440898：上市年份季节；秋冬款 1071720043442：功能/适用场景/是否商场同款）——一次性 heredoc：打开 → clear_overlays → fill_extract_way → fill_prop_gaps(其 gaps) → re-detect。Expected: 对应字段消失。

- [ ] **Step 4: Commit**

```bash
git add automation/sourcing/compliance_filler.py test_compliance_filler.py
git commit -m "feat(sourcing): 属性级合规字段填充(面料/季节/同款/功能/场景)"
```

---

### Task 5: v2 集成 + 6 样本探路验收 + 恢复全量运行

**Files:**
- Modify: `automation/sourcing/assign_shop_category_v2.py`（process_one 集成 + 主循环 skipped 转移）
- Modify: `automation/sourcing/AGENTS.md`（归类 v2 小节补合规填充器说明）
- 运行产物: `cat_v2_run.log`（gitignore）

**Interfaces:**
- Consumes: `clear_overlays/fill_extract_way/detect_gaps/fill_sku_gaps/fill_prop_gaps/is_image_only_failure`（compliance_filler 全量导出）
- Produces: v2 提交前合规链路；`--ids` 探路；恢复 `run_cat_v2.sh --retry-failed` 常驻

- [ ] **Step 1: 集成 process_one**

`assign_shop_category_v2.py`：

1. import 区加：`from compliance_filler import clear_overlays, detect_gaps, fill_extract_way, fill_sku_gaps, fill_prop_gaps`
2. `process_one` 内 `await scroll_edit_page(page)` 与 `rh2 = handle_recommend_dialog(page)` 之后、`lm = await check_listing_mode(page)` 之前插入：

```python
        await clear_overlays(page)   # 新增浮层拦截点击(调价也被拦), 须在一切交互前
```

3. `set_shop_category` 成功分支（`rh3 = handle_recommend_dialog(page)` 之后、`remove_videos` 之前）插入：

```python
        title_txt = title or ''
        gaps = await detect_gaps(page)
        if gaps:
            await clear_overlays(page)
            eok, emsg = await fill_extract_way(page)
            if not eok:
                log(f"  ⚠ 提取方式: {emsg}")
            sok1, smsg1 = await fill_sku_gaps(page, gaps, title_txt)
            if not sok1:
                return 'fail', f'合规SKU填充失败: {smsg1}', None
            pok1, pmsg1 = await fill_prop_gaps(page, gaps, title_txt)
            if not pok1:
                return 'fail', f'合规属性填充失败: {pmsg1}', None
            gaps2 = await detect_gaps(page)
            if gaps2:
                return 'fail', f'合规字段残留: {[g["name"] for g in gaps2]}', None
            log(f"  · 合规填充: {smsg1} | {pmsg1}")
```

4. 主循环 fail 分支（`prog['failed'][item_id] = ...` 之前）改为：

```python
        else:
            fail_c += 1
            if is_image_only_failure(msg):
                if item_id not in prog['skipped']:
                    prog['skipped'].append(item_id)
                prog['failed'].pop(item_id, None)
                log(f"  ⏭ 仅剩盗图(PIC_STEAL), 转 skipped 待换图")
            else:
                prog['failed'][item_id] = {'category': category, 'error': msg}
                log(f"  ✗ {msg}")
```

（`from compliance_filler import is_image_only_failure` 并入第 1 点的 import。）

- [ ] **Step 2: 语法与既有自检**

Run:
```bash
../venv/bin/python -c "import ast; ast.parse(open('assign_shop_category_v2.py').read())"
../venv/bin/python test_collect_list.py && ../venv/bin/python test_plan_merge.py && ../venv/bin/python test_v2_todo.py && ../venv/bin/python test_compliance_filler.py
```
Expected: 全 PASS。`pgrep -f assign_shop_category_v2` 确认无运行实例。

- [ ] **Step 3: 6 样本探路（--ids 定向）**

Run:
```bash
../venv/bin/python assign_shop_category_v2.py --ids 1078910949614,888970440898,1071720043442,1058428800598,1058429056593 2>&1 | tee trail_filler.log
```
Expected: ≥4/5 完整成功（✓ 且含「合规填充」日志行）。家居服样本 `1072552474230` 单独跑：

```bash
../venv/bin/python assign_shop_category_v2.py --ids 1072552474230 2>&1 | tee trail_filler2.log
```
Expected: 合规填充成功后提交失败，且失败信息仅剩图片类（日志出现 `⏭ 仅剩盗图(PIC_STEAL), 转 skipped`，进度里该 ID 进 skipped、不在 failed）。若出现非图片失败 → 附日志报 DONE_WITH_CONCERNS，不得放量。

- [ ] **Step 4: probe 复核成功样本**

从 trail_filler.log 取成功 itemId（≤3 个）：`../venv/bin/python probe_item_state.py <id...>`
Expected: `上架状态=立刻上架` + 分类=plan 目标。

- [ ] **Step 5: 更新 sourcing/AGENTS.md 并提交代码**

AGENTS.md 归类 v2 小节追加一行：
「**合规填充器**（2026-09-25）：平台新增按类目必填（SKU 厚薄/是否加绒/款式，属性 面料/上市年份季节/是否商场同款/功能/适用场景），v2 提交前自动检测填充（compliance_filler.py，页面自带错误态零试提交）；新浮层（sku-preview-iframe/struct-error-board）拦点击，clear_overlays 必须在一切交互前；提取方式旧 JS click 失效改真点击；提交失败仅剩 PIC_STEAL → 转 skipped 待换图。」

```bash
git add automation/sourcing/assign_shop_category_v2.py automation/sourcing/AGENTS.md
git commit -m "feat(sourcing): v2 集成合规填充器, PIC_STEAL-only 转 skipped"
```

- [ ] **Step 6: 恢复全量运行 + 首小时观察**

```bash
nohup ./run_cat_v2.sh --retry-failed > /dev/null 2>&1 &
sleep 30 && tail -5 cat_v2_run.log
```
观察 30 分钟：①`grep -c "✓" cat_v2_run.log` 增长 ②`grep -c "必填项未填" cat_v2_run.log` 新增为 0（PIC_STEAL 除外）③`grep -c "⚠ 风控" cat_v2_run.log` 无连续出现。全部满足 → 报 DONE；否则现场留证报 DONE_WITH_CONCERNS。

## Self-Review 结论

- **Spec 覆盖**：浮层清理（T1/T5）、提取方式修复（T2）、SKU 级（T3）、属性级（T4）、v2 集成+探路+恢复运行（T5）、PIC_STEAL 转移（T2 判定 + T5 集成）——全覆盖；「不做的事」未引入。
- **占位符**：无 TBD；所有代码为完整实现；控件结构未知处通过 Task 1 notes 显式落地为「SELECTORS 常量按 notes 修正」的既定流程，接口签名全程稳定。
- **类型一致性**：`parse_gaps/detect_gaps/is_image_only_failure/sku_value_for/fill_sku_gaps/prop_value_for/season_value/fill_prop_gaps/clear_overlays/fill_extract_way` 命名与签名跨任务一致；gap dict `{'name','zone'}` 结构统一。
- **已知风险**：T3/T4 面板与属性控件结构基于 Fusion 范式推断，Task 1 发现即修正；探路若非图片失败则停在 Task 5 Step 3（不放量）。
