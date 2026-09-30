#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合规填充器: 淘宝 2026-09 新必填字段自动填充. spec: docs/superpowers/specs/2026-09-25-shop-cat-compliance-filler-design.md"""
import asyncio
import datetime
import re

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


async def ensure_no_overlay(page):
    """关闭残留的 next-overlay 下拉弹层. 2026-09-26 根因实证: 上一列选值/页面自带弹层
    未关(单选残留无 Escape)时 'next-overlay-wrapper opened' 挡住后续一切点击,
    裤长/提取方式/属性选择 全部 8s 超时(牛仔短裤 3 样本 + 秋冬款/连衣裙/半身裙)."""
    for _ in range(3):
        opened = await page.evaluate(
            "() => [...document.querySelectorAll('.next-overlay-wrapper.opened')]"
            ".filter(o => o.getClientRects().length > 0).length")
        if not opened:
            return
        await page.keyboard.press('Escape')
        await asyncio.sleep(0.4)


SKU_FIELDS = ('厚薄', '是否加绒', '款式')          # SKU 级(每行)字段
ZONE_EXTRACT, ZONE_SKU, ZONE_PROP = 'extract', 'sku', 'prop'
FIELD_ZONE = {'厚薄': ZONE_SKU, '是否加绒': ZONE_SKU, '款式': ZONE_SKU,
              '面料': ZONE_PROP, '材质成分': ZONE_PROP, '上市年份季节': ZONE_PROP,
              '是否商场同款': ZONE_PROP, '功能': ZONE_PROP, '适用场景': ZONE_PROP,
              '提取方式': ZONE_EXTRACT,
              # 长裤/牛仔短裤实测必填 SKU 列(探路 2026-09-25): msg-bar 报缺但平台必填清单未列
              '裤型': ZONE_SKU, '裤长': ZONE_SKU,
              # 内衣/家居服类新必填属性(探路 2026-09-26 深夜): 内联报错但面板分节不列名
              '适用人群': ZONE_PROP, '风格': ZONE_PROP, '是否带胸垫': ZONE_PROP,
              # 连衣裙/半身裙/秋冬裤类新必填 SKU 列(探路 2026-09-26 深夜)
              '裙长': ZONE_SKU, '适用体型': ZONE_SKU, '图案': ZONE_SKU}
KNOWN_FIELDS = tuple(FIELD_ZONE)  # 对外接口别名, 与 FIELD_ZONE 声明同序
IMAGE_FAIL_MARK = 'PIC_STEAL'
IMAGE_FAIL_CODE = 'CHK_IMAGE_PC_PIC_STEAL'  # 盗图完整错误码自带 CHK_ 前缀, 排除集检查前须抹掉防自伤
FILL_FAIL_MARKS = ('必填', '不能为空', '规格', 'CHK_', '视频', '尺码')  # 混合错误(盗图+其他类)不转换图队列
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
    """提交失败信息是否仅剩图片(盗图)问题(无必填/规格/其他错误码/视频/尺码类错误). 纯函数."""
    if IMAGE_FAIL_MARK not in msg:
        return False
    rest = msg.replace(IMAGE_FAIL_CODE, '')  # 抹掉盗图码自身, 否则其 CHK_ 前缀误命中排除集
    return not any(m in rest for m in FILL_FAIL_MARKS)


async def detect_gaps(page):
    """读页面错误态(自带上次失败态, 零试提交) -> parse_gaps.
    #struct-error-board 可能已被 clear_overlays 隐藏(display:none), body.innerText 读不到
    → 同步 evaluate 内临时还原读 innerText 再隐藏(行结构保留, parse 依赖行);
    board 实测随表单实时重算(填完即消), 初检与 gaps2 复检同样适用. 提取方式类错误只在此板出现."""
    body = await page.evaluate("""() => {
        const b = document.querySelector('#struct-error-board');
        let extra = '';
        if (b && b.style.display === 'none') {
            b.style.display = '';
            extra = b.innerText || '';
            b.style.display = 'none';
        }
        return document.body.innerText + (extra ? '\\n' + extra : '');
    }""")
    return parse_gaps(body)


_EXTRACT_CHECKED_JS = """() => {
    const el = document.querySelector('#sell-field-tbExtractWay');
    if (!el) return null;
    for (const l of el.querySelectorAll('label')) {
        if (/使用物流配送/.test(l.textContent||'')) {
            const i = l.querySelector('input');
            return i ? !!i.checked : null;
        }
    }
    return null;
}"""

_EXTRACT_DUMP_JS = """() => {
    const el = document.querySelector('#sell-field-tbExtractWay');
    if (!el) return null;
    let labelText = '', disabled = null, checked = null, hasInput = false;
    for (const l of el.querySelectorAll('label')) {
        if (/使用物流配送/.test(l.textContent||'')) {
            labelText = (l.textContent||'').replace(/\\s+/g,' ').trim().slice(0, 30);
            const i = l.querySelector('input');
            if (i) { hasInput = true; disabled = !!i.disabled; checked = !!i.checked; }
        }
    }
    return {labelText: labelText, disabled: disabled, checked: checked, hasInput: hasInput,
            hasSelect: !!el.querySelector('span.next-select'),
            raw: (el.innerText||'').replace(/\\s+/g,' ').trim().slice(0, 60)};
}"""


async def fill_extract_way(page):
    """提取方式: 浮层清理后 Playwright 真点「使用物流配送」label, 以 input.checked 翻转为准.
    无效果时一次性 dump 现场定性(前置修正 2026-09-25): DISABLED=需人工 / SELECT 变体走
    _set_next_select / NO_INPUT / 重试点 input 本体+4x0.5s 写回复核.
    返回 (ok, CHECKED|DISABLED:..|SELECT:..|NO_INPUT|NO_EFFECT:..)."""
    zone = page.locator('#sell-field-tbExtractWay')
    if await zone.count() == 0:
        return False, 'NO_ZONE'
    lbl = zone.locator('label', has_text='使用物流配送').first
    if await lbl.count() == 0:
        return False, 'NO_LABEL'
    await ensure_no_overlay(page)
    await lbl.click(timeout=8000)
    await asyncio.sleep(0.8)
    if await page.evaluate(_EXTRACT_CHECKED_JS):
        return True, 'CHECKED'
    d = await page.evaluate(_EXTRACT_DUMP_JS)
    if not d:
        return False, 'NO_ZONE'
    if d.get('disabled'):
        return False, f"DISABLED:提取方式需人工 label={d.get('labelText')!r} raw={d.get('raw')!r}"
    if d.get('hasSelect'):
        picked = await _set_next_select(page, zone, '使用物流配送')
        if picked:
            return True, f'SELECT:{picked}'
        return False, f"NO_EFFECT:SELECT变体未命中 dump={d}"
    if not d.get('hasInput'):
        return False, f"NO_INPUT dump={d}"
    try:
        await lbl.locator('input').first.click(timeout=4000)
    except Exception:
        try:
            await page.evaluate("""() => {
                const el = document.querySelector('#sell-field-tbExtractWay');
                for (const l of el.querySelectorAll('label')) {
                    if (/使用物流配送/.test(l.textContent||'')) {
                        const i = l.querySelector('input');
                        if (i) { i.click(); return; }
                    }
                }
            }""")
        except Exception:
            pass
    for _ in range(4):
        await asyncio.sleep(0.5)
        if await page.evaluate(_EXTRACT_CHECKED_JS):
            return True, 'CHECKED'
    return False, f"NO_EFFECT:label点击与input重试均无效 dump={d}"


SKU_DEFAULTS = {'厚薄': '常规', '是否加绒': '否'}
JIA_RONG_KW = ('加绒', '绒')


def _is_cn(ch):
    return '\u4e00' <= ch <= '\u9fff'


def _share_cn_sub2(a, b):
    """a/b 是否有公共子串(≥2 连续中文字符)=a 存在相邻中文二字组出现在 b 中. 纯函数."""
    for i in range(len(a) - 1):
        if _is_cn(a[i]) and _is_cn(a[i + 1]) and a[i:i + 2] in b:
            return True
    return False


def _opt_match(opts, title, fallback=None, extra_kw=(), first_fallback=True):
    """选项取值: 标题含选项名(长优先) > 别名关键词命中 > 指定兜底 > 首项(可关). 纯函数."""
    opts = [o for o in (opts or []) if o]
    hits = [o for o in opts if o in (title or '')]
    if hits:
        return max(hits, key=len)
    for val, kws in extra_kw:
        if val in opts and any(k in (title or '') for k in kws):
            return val
    if fallback and fallback in opts:
        return fallback
    return opts[0] if (opts and first_fallback) else ''


def sku_value_for(field, title, options=None):
    """SKU 属性取值. 命名字段(厚薄/是否加绒/款式)规则不变; 未知字段(裤型/裤长等)标题匹配优先——
    取与 title 有公共子串(≥2 连续中文)的首个选项, 无匹配返回 None(F-B: 绝不写首项猜测值)."""
    title = title or ''
    if field == '是否加绒':
        return '是' if any(k in title for k in JIA_RONG_KW) else '否'
    if field in SKU_DEFAULTS:
        v = SKU_DEFAULTS[field]
        if options:
            for o in options:
                if o == v:
                    return v
            return options[0]
        return v
    opts = [o for o in (options or []) if o]
    if field == '款式':  # 命名字段规则不变: 标题含选项名者优选(长选项优先), 无命中首项兜底
        if opts:
            hits = [o for o in opts if o in title]
            return max(hits, key=len) if hits else opts[0]
        return ''
    if field == '裙长':   # 2026-09-26 探路: 半身裙/连衣裙必填, 中裙兜底(最中性)
        return _opt_match(opts, title, fallback='中裙')
    if field == '图案':   # 半身裙/牛仔类必填 SKU 列: 标题图案词命中, 纯色兜底
        return _opt_match(opts, title, fallback='纯色')
    if field == '适用体型':   # 连衣裙必填, 通用型兜底
        return _opt_match(opts, title, fallback='通用型')
    if field == '裤长':   # 公共子串匹配(九分牛→九分裤) > 语义别名(直筒→长裤) > 留人工(禁首项兜底)
        hits = [o for o in opts if _share_cn_sub2(o, title)]
        if hits:
            return max(hits, key=len)
        for val, kws in (('长裤', ('直筒', '阔腿', '小脚', '拖地', '垂感')),):
            if val in opts and any(k in title for k in kws):
                return val
        return None
    for o in opts:  # 未知字段: 公共子串匹配优先
        if _share_cn_sub2(o, title):
            return o
    return None


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
    选值即时写回表单态无需确认; 填充后 re-detect 由调用方负责.
    探路修正(2026-09-25): 占位符'请选择'不算已有值; async-select 弹层延迟出现须轮询;
    多选(next-select-multiple)弹层不自动关须 Escape, 写回态='… '+tag 文本, 校验按含值判定.
    未知字段无匹配(F-B): 跳过该字段记'=无匹配需人工', 残留 gap 由 re-detect/提交校验兜底, 绝不写猜测值."""
    sku_gaps = [g for g in gaps if g['zone'] == ZONE_SKU]
    if not sku_gaps:
        return True, 'no sku gaps'
    done, manual_skipped = [], []
    for g in sku_gaps:
        field = g['name']
        try:
            info = await page.evaluate(_PROP_CELL_JS, field)
            if 'err' in info:
                return False, f'{field}: {info["err"]}'
            prop, n_rows = info['prop'], info['nRows']
            value, filled, is_multi, manual = None, 0, None, False
            for i in range(n_rows):
                trig = page.locator(
                    f'#sell-field-sku [id="{i}-skuParam_p-{prop}"] span.next-select').first
                if await trig.count() == 0:
                    continue
                if is_multi is None:
                    is_multi = 'next-select-multiple' in (
                        (await trig.get_attribute('class', timeout=3000)) or '')
                cur = (await trig.inner_text()).strip()
                if cur and cur != '请选择':  # 已有值: 不覆盖(重跑幂等)
                    filled += 1
                    value = value or cur
                    continue
                await ensure_no_overlay(page)
                await trig.click(timeout=8000)
                options = None
                for _ in range(8):  # async-select 弹层延迟出现, 0.5s x8 轮询
                    await asyncio.sleep(0.5)
                    options = await page.evaluate(_READ_OPTIONS_JS)
                    if options:
                        break
                if not options:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    return False, f'{field}: 行{i}下拉无选项'
                value = sku_value_for(field, title, options)
                if value is None:  # 无匹配: 绝不写猜测值, 留 gap 交人工(商品进 failed 可诊断)
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    manual = True
                    break
                opt = page.locator(SKU_PANEL['option'] + f'[title="{value}"]').last
                if await opt.count() == 0:  # 取值不在选项(虚拟滚动等)兜底
                    opt = page.locator(SKU_PANEL['option']).last
                if await opt.count() == 0:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(0.5)
                    return False, f'{field}: 行{i}下拉无选项'
                await opt.click(timeout=8000)
                if is_multi:  # 多选弹层不自动关, 且挡下一行 trigger, 必须关
                    await page.keyboard.press('Escape')
                ok = False
                for _ in range(4):  # 选值写回校验: 多选='… '+tag 文本; combobox=内部 input.value(裤长实证), 按含值判定
                    await asyncio.sleep(0.5)
                    ok = await page.evaluate("""(a) => {
                        const td = document.getElementById(a[0]);
                        if (!td) return false;
                        const inp = td.querySelector('input');
                        if (inp && (inp.value||'').trim() === a[1]) return true;
                        const sel = td.querySelector('span.next-select');
                        if (sel && (sel.innerText||'').includes(a[1])) return true;
                        return [...td.querySelectorAll('.next-tag-body')].some(
                            e => (e.innerText||'').trim() === a[1]);
                    }""", [f'{i}-skuParam_p-{prop}', value])
                    if ok:
                        break
                if not ok:
                    return False, f'{field}: 行{i}选值未生效'
                filled += 1
            if manual:  # 跳过该字段不视为填充成功
                manual_skipped.append(f'{field}=无匹配需人工')
                continue
            if filled == 0:
                return False, f'{field}: 0行填充(prop={prop})'
            done.append(f'{field}={value}({filled}行)')
        except Exception as e:
            return False, f'{field}: {str(e)[:60]}'
    segs = []
    if done:
        segs.append('filled ' + ','.join(done))
    if manual_skipped:
        segs.append('人工:' + ','.join(manual_skipped))
    if not segs:
        return True, 'no sku fills'
    return True, ' | '.join(segs)


# ---------------- 属性级填充 (Task 4) ----------------
# 控件结构以 compliance_ui_notes.md 为准(brief 的 .next-form-item/.next-menu-item 假设落空):
# 字段定位=label 文本上溯 [id^="sell-field-p-"]; 下拉弹层 .next-select-popup-wrap,
# 选项 .options-item[title], 弹层内 .options-search input 可过滤虚拟滚动; 材质成分=字段内联展开。
PROP_KEYWORDS = {
    '功能': (('保暖', ('保暖', '加绒', '加厚', '毛绒', '羽绒')), ('透气', ())),
    '适用场景': (('居家', ('睡衣', '睡裙', '家居服', '居家')), ('日常', ())),
    '面料': (('牛仔布', ('牛仔',)), ('聚酯纤维', ())),
    # 2026-09-26 探路新增(内衣/家居服新必填属性; 选项已实地核读):
    '是否带胸垫': (('是', ('胸垫', '聚拢')), ('否', ())),
    '适用人群': (('特殊体型女性', ('大码', '胖', '微胖', '加大')),
                 ('运动爱好者', ('运动', '瑜伽', '健身', '跑步')),
                 ('青少年女性', ('青少年', '学生', '初中', '高中')),
                 ('成年女性', ('女',))),
    '风格': (('优雅风', ('优雅', '温柔', '轻奢', '法式')), ('可爱风', ('可爱', '卡通', '甜美', '公主')),
             ('休闲风', ('休闲', '慵懒', '宽松', '简约', '百搭', '基础'))),
}
PROP_CONST = {'是否商场同款': ['否'], '材质成分': ['聚酯纤维:100']}
PROP_UI = {
    'label': '.sell-component-info-wrapper-label',
    'field': '[id^="sell-field-p-"]',
    'trigger': 'span.next-select',
    'popup': '.next-overlay-wrapper.opened .next-select-popup-wrap',
    'search': '.options-search input',
    'option': '.options-item',
    'mat_add': 'button.add-new',
    'mat_row': '.material-item',
    'mat_input': 'input[placeholder="输入含量"]',
}
PROP_LABEL_ALIAS = {'上市年份季节': ('上市年份季节', '上市时间'),       # 美甲类 label=上市时间
                    '材质成分': ('材质成分', '面料材质成分')}          # 服装类 label=面料材质成分


def season_value():
    d = datetime.date.today()
    m = d.month
    ji = '春' if m <= 3 else '夏' if m <= 6 else '秋' if m <= 9 else '冬'
    return f'{d.year}年{ji}季'


def prop_value_for(field, title):
    """返回候选值序列(依次尝试, 标题关键词命中优先). 材质成分特殊: '材质:含量' 列表."""
    if field in PROP_CONST:
        return list(PROP_CONST[field])
    if field == '上市年份季节':
        return [season_value()]
    cands = []
    for val, kws in PROP_KEYWORDS.get(field, ()):
        if any(k in (title or '') for k in kws):
            cands.append(val)
    if PROP_KEYWORDS.get(field):
        last = PROP_KEYWORDS[field][-1][0]
        if last not in cands:
            cands.append(last)   # 默认兜底 = 最后一个候选
    return cands


_PROP_FIELD_JS = """(names) => {
  for (const n of names) {
    for (const l of document.querySelectorAll('.sell-component-info-wrapper-label')) {
      const t = (l.innerText || '').replace(/\\*|\\s|重要|必填/g, '');
      if (t !== n) continue;
      const el = l.closest('[id^="sell-field-p-"]');
      if (!el || el.closest('.next-drawer')) continue;  // 抽屉内同构字段壳不算
      return el.id;
    }
  }
  return null;
}"""


async def _set_next_select(page, box, value):
    """容器 box 内 next-select 单/多选填值: 展开->弹层搜索过滤(虚拟滚动)->按 title 选->写回校验.
    候选无精确匹配时回落弹层首个可见选项(合规目标=非空). 返回实际写回值, 无可选返回 None.
    注意: 单选点选项后弹层即关/选项节点 detach, 选项 title 必须点击前取;
    显式 timeout 兜底, 防默认 30s 挂起把已成功的选值误判为失败."""
    trig = box.locator(PROP_UI['trigger']).first
    if await trig.count() == 0:
        return None
    is_multi = 'next-select-multiple' in ((await trig.get_attribute('class', timeout=3000)) or '')
    await trig.click(timeout=8000)
    await asyncio.sleep(0.8)
    popup = page.locator(PROP_UI['popup']).last
    if await popup.count() == 0:
        await page.keyboard.press('Escape')
        return None
    picked = None
    try:
        s = popup.locator(PROP_UI['search'])
        has_search = await s.count() > 0 and await s.first.is_visible()
        if has_search:
            await s.first.fill(value, timeout=5000)
            await asyncio.sleep(0.8)
        opt = popup.locator(f'{PROP_UI["option"]}[title="{value}"]').first
        if await opt.count() == 0:   # 无精确匹配: 清搜索回落全部可见选项
            if has_search:
                await s.first.fill('', timeout=5000)
                await asyncio.sleep(0.8)
            opt = popup.locator(PROP_UI['option']).first
        if await opt.count() == 0:
            return None
        picked = await opt.get_attribute('title', timeout=3000) or value
        await opt.click(timeout=8000)
        await asyncio.sleep(0.6)
    finally:
        if is_multi:   # 多选弹层不自动关
            try:
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
            except Exception:
                pass
    try:
        txt = (await trig.inner_text(timeout=5000)).strip()
    except Exception:
        txt = ''
    if picked and (value in txt or picked in txt or '已选择' in txt):
        return picked
    return None


async def _fill_material(page, title):
    """材质成分组合(服装类目): label 定位字段->「添加材质成分」内联展开->搜索选材质->含量 100.
    已有材质行不覆盖(含量总和须=100, 重跑幂等). 长裤=普通文本输入/美甲=材质下拉, 类目不同不匹配."""
    names = list(PROP_LABEL_ALIAS['材质成分'])
    cid = await page.evaluate(_PROP_FIELD_JS, names)
    if not cid:
        return False, '材质成分: 表单项未找到'
    box = page.locator(f'#{cid}')
    if await box.locator(f'{PROP_UI["mat_row"]} em[title]').count() > 0:
        return True, '材质成分=已填(跳过)'
    add = box.locator(PROP_UI['mat_add'], has_text='添加材质成分')
    if await add.count() == 0:
        return False, '材质成分: 添加按钮未找到'
    await add.first.click(timeout=8000)   # 内联展开, 无 dialog/drawer
    await asyncio.sleep(1.2)
    mat, _, pct = prop_value_for('材质成分', title)[0].partition(':')
    row = box.locator(PROP_UI['mat_row']).first
    trig = row.locator(PROP_UI['trigger']).first
    if await trig.count() == 0:
        return False, '材质成分: 材质下拉未出现'
    await trig.click(timeout=8000)
    await asyncio.sleep(0.8)
    popup = page.locator(PROP_UI['popup']).last
    if await popup.count() == 0:
        return False, '材质成分: 材质弹层未出现'
    s = popup.locator(PROP_UI['search'])
    if await s.count() > 0 and await s.first.is_visible():
        await s.first.fill(mat, timeout=5000)
        await asyncio.sleep(0.8)
    opt = popup.locator(f'{PROP_UI["option"]}[title="{mat}"]').first
    if await opt.count() == 0:
        await page.keyboard.press('Escape')
        return False, f'材质成分: 选项{mat}未命中'
    await opt.click(timeout=8000)
    await asyncio.sleep(0.8)
    inp = row.locator(PROP_UI['mat_input']).first   # 选中材质后才出现
    if await inp.count() == 0:
        await asyncio.sleep(1.0)
    if await inp.count() > 0:
        await inp.fill(pct)
        await asyncio.sleep(0.4)
    return True, f'材质成分={mat}{pct}'


async def fill_prop_gaps(page, gaps, title):
    """属性级缺失填充(zone=prop): 材质成分=内联展开添加; 其余=label 定位字段容器后
    单/多选下拉填值(虚拟滚动先搜索). 是否商场同款类目缺失时跳过不报错. 不含提交."""
    done = []
    for g in [g for g in gaps if g['zone'] == ZONE_PROP]:
        field = g['name']
        try:
            await clear_overlays(page)   # React 重渲染会复位隐藏, 每字段前重调
            if field == '材质成分':
                ok, msg = await _fill_material(page, title)
                if not ok:
                    return False, msg
                done.append(msg)
                continue
            cid = await page.evaluate(_PROP_FIELD_JS, list(PROP_LABEL_ALIAS.get(field, (field,))))
            if not cid:
                if field == '是否商场同款':
                    continue   # notes 差异#7: 仅部分类目有, 无此字段=无校验, 跳过
                return False, f'{field}: 表单项未找到'
            box = page.locator(f'#{cid}')
            await ensure_no_overlay(page)
            cands = prop_value_for(field, title)
            picked = None
            for v in cands:
                try:
                    picked = await _set_next_select(page, box, v)
                except Exception:
                    picked = None
                if picked:
                    break
            if not picked:
                return False, f'{field}: 候选值均未命中{cands}'
            done.append(f'{field}={picked}')
        except Exception as e:
            return False, f'{field}: {str(e)[:60]}'
    if not done:
        return True, 'no prop gaps'
    return True, 'filled ' + ','.join(done)


# ============ SKU 颜色【】清洗 (2026-09-26) ============
# 穿戴甲 SKU 颜色值带 1688 元数据【甲型】(如 'XS 黑粉千金【细狗尖】'), 淘宝校验拒绝【】→ 颜色分类填写错误
# (08-29 ISV 铺货 32 个同因)。08-29 试单元格点击/fiber 直改均不可写; 2026-09-26 发现「编辑规格」
# 对话框主色 input 可编辑, 确认创建重建 SKU 表实测 3 样本(含 8 SKU 双甲型)价格/库存/行结构原样保留。
# 规则: 【x】→-x (保留甲型文本防重名, 只去被拒括号); 清洗后重名/空值 → 留人工(CLEAN_MANUAL)。

_COLOR_READ_JS = """() => {
  const hs = [...document.querySelectorAll('.sell-sku-table-header-common-new')];
  let idx = hs.findIndex(e => (e.innerText||'').trim() === '颜色分类');
  if (idx < 0) idx = 1;
  const vals = [];
  for (const tr of document.querySelectorAll('#sell-field-sku tr')) {
    const td = tr.children[idx];
    if (!td) continue;
    const sp = td.querySelector('span[title]');
    const v = sp ? (sp.getAttribute('title')||'') : (td.innerText||'').trim();
    if (v) vals.push(v);
  }
  return vals;
}"""


def clean_color_value(v):
    """纯函数: 颜色值清洗. 'XS 薄荷绿【细狗尖】' -> 'XS 薄荷绿-细狗尖'."""
    out = re.sub(r'\s*【([^】]*)】', r'-\1', v or '').strip()
    return re.sub(r' {2,}', ' ', out)


async def clean_sku_color_brackets(page):
    """颜色值含【】时经「编辑规格」对话框清洗并确认创建重建 SKU 表。
    返回 (changed, msg): True=已重建(调用方须重新 clear_overlays, 且重建可能清掉已填参数列,
    故必须在调价/合规填充之前跑); False+'no dirty'=无脏值零开销; False+'CLEAN_MANUAL:'=留人工。"""
    try:
        vals = await page.evaluate(_COLOR_READ_JS)
    except Exception as e:
        return False, f'读取颜色失败: {str(e)[:50]}'
    if not vals:
        return False, 'no dirty'
    dirty = [v for v in vals if '【' in v]
    if not dirty:
        return False, 'no dirty'
    cleaned = [clean_color_value(v) for v in vals]
    dups = sorted({c for c in cleaned if cleaned.count(c) > 1})
    if dups:
        return False, f'CLEAN_MANUAL: 清洗后重名{dups[:2]}'
    if any(not c for c in cleaned):
        return False, 'CLEAN_MANUAL: 清洗后出现空值'
    btn = page.locator('#sell-field-sku button:has-text("编辑规格")').first
    if await btn.count() == 0:
        return False, 'CLEAN_MANUAL: 无编辑规格按钮'
    await btn.click(timeout=8000)
    # 可能的警告确认框(实测通常无); 只点 .next-dialog 层确定, 最多 2 轮
    for _ in range(2):
        await asyncio.sleep(1)
        dlg = page.locator('.next-dialog:visible button:has-text("确定"), .next-dialog:visible button:has-text("继续")').first
        if await dlg.count() > 0:
            await dlg.click(timeout=5000)
        else:
            break
    inputs = page.locator('.next-overlay-wrapper.opened input[placeholder="主色(必选)"]')
    n = await inputs.count()
    if n != len(vals):
        await page.keyboard.press('Escape')
        return False, f'CLEAN_MANUAL: 主色输入框{n}!=SKU行{len(vals)}'
    changed = 0
    for i in range(n):
        el = inputs.nth(i)
        v = (await el.input_value()).strip()
        c = clean_color_value(v)
        if c != v:
            await el.fill(c)
            changed += 1
            await asyncio.sleep(0.2)
    await page.locator('button:has-text("确认创建")').first.click(timeout=8000)
    await asyncio.sleep(2.5)
    guard = page.locator('.next-dialog:visible button:has-text("确定")').first
    if await guard.count() > 0:
        await guard.click(timeout=5000)
        await asyncio.sleep(1.5)
    after = await page.evaluate(_COLOR_READ_JS)
    if any('【' in v for v in after):
        return False, f'重建后仍有【】{after[:2]}'
    if len(after) != len(vals):
        return False, f'重建后行数变化 {len(vals)}->{len(after)}'
    if not changed:
        return False, 'no dirty'
    return True, f'清洗 {changed} 个颜色值并重建SKU表(价格/库存保留)'


async def sku_colors_dirty(page):
    """SKU 颜色列是否含【】(穿戴甲 1688 元数据, 淘宝校验拒绝). 零交互快速探测."""
    vals = await page.evaluate(_COLOR_READ_JS)
    return any('【' in v for v in vals)
