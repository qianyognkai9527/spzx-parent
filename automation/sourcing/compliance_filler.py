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


SKU_FIELDS = ('厚薄', '是否加绒', '款式')          # SKU 级(每行)字段
ZONE_EXTRACT, ZONE_SKU, ZONE_PROP = 'extract', 'sku', 'prop'
FIELD_ZONE = {'厚薄': ZONE_SKU, '是否加绒': ZONE_SKU, '款式': ZONE_SKU,
              '面料': ZONE_PROP, '材质成分': ZONE_PROP, '上市年份季节': ZONE_PROP,
              '是否商场同款': ZONE_PROP, '功能': ZONE_PROP, '适用场景': ZONE_PROP,
              '提取方式': ZONE_EXTRACT}
KNOWN_FIELDS = tuple(FIELD_ZONE)  # 对外接口别名, 与 FIELD_ZONE 声明同序
IMAGE_FAIL_MARK = 'PIC_STEAL'
FILL_FAIL_MARKS = ('必填', '不能为空', '规格')
ERROR_LINE_TOKENS = ('必填项未填', '必填项不能为空')  # 错误面板汇总行 / 字段内联错误行(1072552474230 实测)
LABEL_LOOKBACK = 10  # 内联错误行距字段 label 行的最大非空行距(实测 7)


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
               (line in ERROR_LINE_TOKENS and _prev_label_is(body_text, name)):
                hit = True
                break
        if hit and name not in seen:
            seen.add(name)
            gaps.append({'name': name, 'zone': FIELD_ZONE[name]})
    return gaps


def _prev_label_is(text, name):
    """错误行归属: 字段名行后 LOOKBACK 行内出现错误行则命中;
    途中遇到其他已知字段 label 则错误属于更近字段, 提前终止(最近归属)."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for i, l in enumerate(lines):
        if l == name or l.endswith(name):
            for nxt in lines[i + 1:i + 1 + LABEL_LOOKBACK]:
                if nxt in ERROR_LINE_TOKENS:
                    return True
                if nxt in FIELD_ZONE:
                    break
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


# 「去填写」面板实测(compliance_ui_notes.md 末尾 task3 补记): 非批量弹层, 而是 SKU 表格内联下拉列——
# 表头 .sell-sku-table-header-common-new 文本=字段名, 数据行单元格 id={行号}-skuParam_p-{propId}
# (propId 随类目变, 由表头文本反查列号取行内 propId); 行内选值即时写回主表单态, 无需确认。
# 抽屉路径(行内「去填写」→ 右侧抽屉)的「确定」会被该行其他未知必填字段(长裤实测: 裤型/裤长)拦死, 不可用。
SKU_PANEL = {
    'header': '.sell-sku-table-header-common-new',          # 表头单元格, 文本=字段名
    'row': '#sell-field-sku tr',                            # SKU 数据行(tr)
    'trigger': 'span.next-select',                          # 单元格内下拉 trigger
    'option': '.next-overlay-wrapper.opened .options-item',  # 下拉选项, title=值
}

_PROP_CELL_JS = """(field) => {
  const hs = [...document.querySelectorAll('.sell-sku-table-header-common-new')];
  const idx = hs.findIndex(e => (e.innerText || '').trim() === field);
  if (idx < 0) return {err: 'NO_HEADER'};
  const tr = document.querySelector('#sell-field-sku tr');
  if (!tr) return {err: 'NO_ROWS'};
  const td = tr.children[idx];
  if (!td) return {err: 'NO_CELL'};
  const m = (td.id || '').match(/skuParam_p-(\\d+)$/);
  if (!m || !td.querySelector('span.next-select')) return {err: 'NOT_PARAM_SELECT', id: td.id};
  return {prop: m[1], nRows: document.querySelectorAll('#sell-field-sku tr').length};
}"""

_READ_OPTIONS_JS = """() => {
  const wraps = [...document.querySelectorAll('.next-overlay-wrapper.opened')];
  if (!wraps.length) return [];
  const w = wraps[wraps.length - 1];
  return [...w.querySelectorAll('.options-item')]
      .map(e => e.getAttribute('title') || (e.innerText || '').trim())
      .filter(Boolean).slice(0, 30);
}"""


async def fill_sku_gaps(page, gaps, title):
    """SKU 级缺失填充: SKU 表格内联下拉列逐行选值(表头文本定位列, 单元格 id 定位行),
    选值即时写回表单态无需确认; 填充后 re-detect 由调用方负责."""
    sku_gaps = [g for g in gaps if g['zone'] == ZONE_SKU]
    if not sku_gaps:
        return True, 'no sku gaps'
    done = []
    for g in sku_gaps:
        field = g['name']
        try:
            info = await page.evaluate(_PROP_CELL_JS, field)
            if 'err' in info:
                return False, f'{field}: {info["err"]}'
            prop, n_rows = info['prop'], info['nRows']
            value, filled = None, 0
            for i in range(n_rows):
                trig = page.locator(
                    f'#sell-field-sku [id="{i}-skuParam_p-{prop}"] span.next-select').first
                if await trig.count() == 0:
                    continue
                cur = (await trig.inner_text()).strip()
                if cur:  # 已有值: 不覆盖(重跑幂等)
                    filled += 1
                    value = value or cur
                    continue
                await trig.click(timeout=8000)
                await asyncio.sleep(1.0)
                options = await page.evaluate(_READ_OPTIONS_JS)
                value = sku_value_for(field, title, options)
                opt = page.locator(SKU_PANEL['option'] + f'[title="{value}"]').last
                if await opt.count() == 0:  # 取值不在选项(虚拟滚动等)兜底第一项
                    opt = page.locator(SKU_PANEL['option']).last
                if await opt.count() == 0:
                    return False, f'{field}: 行{i}下拉无选项'
                await opt.click(timeout=8000)
                ok = False
                for _ in range(4):  # 选值写回校验
                    await asyncio.sleep(0.5)
                    if (await trig.inner_text()).strip() == value:
                        ok = True
                        break
                if not ok:
                    return False, f'{field}: 行{i}选值未生效'
                filled += 1
            if filled == 0:
                return False, f'{field}: 0行填充(prop={prop})'
            done.append(f'{field}={value}({filled}行)')
        except Exception as e:
            return False, f'{field}: {str(e)[:60]}'
    return True, 'filled ' + ','.join(done)
