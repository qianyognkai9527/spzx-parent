#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合规填充器: 淘宝 2026-09 新必填字段自动填充. spec: docs/superpowers/specs/2026-09-25-shop-cat-compliance-filler-design.md"""
import asyncio
import datetime

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
              '提取方式': ZONE_EXTRACT,
              # 长裤/牛仔短裤实测必填 SKU 列(探路 2026-09-25): msg-bar 报缺但平台必填清单未列
              '裤型': ZONE_SKU, '裤长': ZONE_SKU}
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


def sku_value_for(field, title, options=None):
    """SKU 属性取值. options: 面板内可选项; 无默认值字段(款式/裤型/裤长等)标题含选项名者
    优选中(长选项优先防 '超短裤' 被 '短裤' 抢先), 无命中取第一项(合规目标=非空)."""
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
    opts = [o for o in (options or []) if o]
    if opts:
        hits = [o for o in opts if o in (title or '')]
        if hits:
            return max(hits, key=len)
        return opts[0]
    return ''


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
    多选(next-select-multiple)弹层不自动关须 Escape, 写回态='… '+tag 文本, 校验按含值判定."""
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
            value, filled, is_multi = None, 0, None
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
                for _ in range(4):  # 选值写回校验: 多选='… '+tag 文本, 须按含值/标签判定
                    await asyncio.sleep(0.5)
                    ok = await page.evaluate("""(a) => {
                        const td = document.getElementById(a[0]);
                        if (!td) return false;
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
            if filled == 0:
                return False, f'{field}: 0行填充(prop={prop})'
            done.append(f'{field}={value}({filled}行)')
        except Exception as e:
            return False, f'{field}: {str(e)[:60]}'
    return True, 'filled ' + ','.join(done)


# ---------------- 属性级填充 (Task 4) ----------------
# 控件结构以 compliance_ui_notes.md 为准(brief 的 .next-form-item/.next-menu-item 假设落空):
# 字段定位=label 文本上溯 [id^="sell-field-p-"]; 下拉弹层 .next-select-popup-wrap,
# 选项 .options-item[title], 弹层内 .options-search input 可过滤虚拟滚动; 材质成分=字段内联展开。
PROP_KEYWORDS = {
    '功能': (('保暖', ('保暖', '加绒', '加厚', '毛绒', '羽绒')), ('透气', ())),
    '适用场景': (('居家', ('睡衣', '睡裙', '家居服', '居家')), ('日常', ())),
    '面料': (('牛仔布', ('牛仔',)), ('聚酯纤维', ())),
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
