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
