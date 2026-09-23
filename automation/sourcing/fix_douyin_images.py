"""fix_douyin_images.py — 抖店已建商品补图: 主图补到5张, 详情图补到≥10张

前置: fix_scrape_images.py 已把对应 offer 的数据补齐 (image_fix_progress.json done)
流程: offer→product_id (draft_match + 店铺列表标题匹配) → 编辑页(有草稿先删)
      → 数现有主图/详情图 → 补传 → 发布商品 → 成功标记
进度: douyin_image_fix_progress.json (done/failed)
用法:
  python fix_douyin_images.py [--limit N] [--test]
  轮询模式: 补采没跑完的会自动等下一轮, 适合与补采并行挂着跑
"""
import asyncio
import json
import os
import random
import re
import sys
import time

from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9223"
DATA = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_product_data.jsonl"
DRAFT_MATCH = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/draft_match.json"
CREATE_PROGRESS = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_create_progress.json"
FIX_SCRAPE_PROGRESS = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/image_fix_progress.json"
PROGRESS = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_image_fix_progress.json"
EDIT_URL = "https://fxg.jinritemai.com/ffa/g/create?product_id={pid}"

sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing")
from gen_optimization_package import clean_title  # noqa: E402


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def compute_title(rec):
    title = rec.get('title') or ''
    had_guiruo = '瑰若' in title
    title = clean_title(title)
    if had_guiruo and not title.startswith('瑰若'):
        title = '瑰若' + title
    if len(title) > 30:
        title = title[:30]
    return title


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_progress(p):
    tmp = PROGRESS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PROGRESS)


async def fetch_store_map(page):
    """店铺全部商品 标准化标题→product_id (离线+在线两个tab)"""
    m = {}
    for tab in ('offline', 'online'):
        pg = 1
        while pg <= 40:
            try:
                url = f"https://fxg.jinritemai.com/product/tproduct/list?page={pg}&pageSize=100&tab={tab}"
                res = await page.evaluate("""async (u) => {
                    const r = await fetch(u, {credentials:'include'});
                    return await r.json();
                }""", url)
            except Exception:
                await asyncio.sleep(2)
                break
            items = res.get('data') or []
            if not items:
                break
            for it in items:
                name = re.sub(r'\s+', '', it.get('name') or '')
                pid = str(it.get('product_id') or '')
                if name and pid and name[:10] not in m:
                    m[name[:10]] = pid
            if len(items) < 100:
                break
            pg += 1
            await asyncio.sleep(0.6)
    return m


async def delete_draft_if_any(page):
    """编辑页若有'已存草稿'先删掉(否则保存的是草稿, 线上商品不更新)"""
    try:
        t = await page.evaluate("document.body.innerText.slice(0,3000)")
        if '已存草稿' not in t:
            return True
        btn = page.locator("button:has-text('删除草稿'), text=删除草稿").first
        await btn.click(timeout=5000)
        await asyncio.sleep(2)
        # 确认弹窗
        for txt in ('确定', '确认', '删除'):
            try:
                dlg_btn = page.locator(f".ecom-g-modal button:has-text('{txt}'), .ant-modal button:has-text('{txt}'), [class*='modal'] button:has-text('{txt}')").first
                if await dlg_btn.is_visible(timeout=2000):
                    await dlg_btn.click(timeout=3000)
                    break
            except Exception:
                continue
        await asyncio.sleep(6)
        await page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(10)
        t2 = await page.evaluate("document.body.innerText.slice(0,3000)")
        log("  · 已删草稿, 重载编辑页")
        return '已存草稿' not in t2
    except Exception as e:
        log(f"  ⚠ 删草稿异常: {str(e)[:60]}")
        return False


async def count_form_images(page):
    """数编辑页 主图区/详情区 现有图片数 (按 section 类名精确定位)"""
    return await page.evaluate("""() => {
        const mainSec = document.querySelector('[class*="mainImg"]');
        const detSec = document.querySelector('[class*="detailImg"]');
        const cnt = (sec) => sec ? sec.querySelectorAll('img').length : -1;
        return {mainN: cnt(mainSec), detN: cnt(detSec),
                mainFI: mainSec ? mainSec.querySelectorAll('input[type=file]').length : 0,
                detFI: detSec ? detSec.querySelectorAll('input[type=file]').length : 0};
    }""")


async def upload_main_imgs(page, files, need):
    """向主图区空槽补传: 空槽 input 的 parent 带 button 类(实测), 传一张数一张, 够5张停"""
    import hashlib
    main_sec = page.locator('[class*="mainImg"]').first
    # 内容去重: 同内容文件平台会按 hash 去重, 传了也白传
    seen_md5 = set()
    uniq = []
    for f in files:
        try:
            h = hashlib.md5(open(f, 'rb').read()).hexdigest()
        except Exception:
            h = f
        if h not in seen_md5:
            seen_md5.add(h)
            uniq.append(f)
    pool = list(reversed(uniq))  # 店里已有的图=池前N张(平台按内容去重), 从池尾倒着传
    uploaded = 0
    ki = 0
    for k in range(need):
        before = int((await count_form_images(page))['mainN'] or 0)
        if before >= 5:
            break
        placed = False
        fis = main_sec.locator("input[type=file]")
        n = await fis.count()
        if n == 0:
            break
        # 空槽优先: parent class 含 button; 其余作备选
        order = []
        for i in range(n):
            try:
                pcls = await fis.nth(i).evaluate("el => (el.parentElement?.className||'').toString()")
            except Exception:
                pcls = ''
            order.append((i, 'button' in pcls))
        order.sort(key=lambda t: 0 if t[1] else 1)
        for i, _free in order:
            fpath = pool[ki % len(pool)]
            try:
                await fis.nth(i).set_input_files([fpath], timeout=30000)
                await asyncio.sleep(6)
                after = int((await count_form_images(page))['mainN'] or 0)
                if after > before:
                    uploaded += 1
                    placed = True
                    ki += 1
                    break
                # 没涨: 重复图被平台去重, 换池中下一个文件
                ki += 1
            except Exception:
                continue
        if not placed:
            log(f"  ⚠ 主图第{k+1}张补传失败(试完所有槽位)")
            try:
                diag = await page.evaluate("""() => {
                    const sec = document.querySelector('[class*="mainImg"]');
                    if (!sec) return 'NO_SECTION';
                    const fis = [...sec.querySelectorAll('input[type=file]')];
                    return {
                        imgs: sec.querySelectorAll('img').length,
                        inputs: fis.map((fi,i) => ({i, disabled: fi.disabled, accept: fi.accept,
                            multiple: fi.hasAttribute('multiple'),
                            pcls: (fi.parentElement?.className||'').toString().slice(0,50),
                            html: fi.outerHTML.slice(0,120)})),
                        secHead: sec.outerHTML.slice(0, 300)
                    };
                }""")
                log(f"  [诊断] {json.dumps(diag, ensure_ascii=False)[:800]}")
            except Exception as e:
                log(f"  [诊断失败] {str(e)[:60]}")
            break
    return uploaded


async def upload_detail_imgs(page, files, have):
    """补详情图到≥10张: 池尾倒序、分批传、传后数, 不够继续; 返回 (是否执行, 最终是否≥10)"""
    if not files:
        return False, False
    det_sec = page.locator('[class*="detailImg"]').first
    if await det_sec.count() == 0:
        return False, False
    try:
        await det_sec.scroll_into_view_if_needed(timeout=8000)
        await asyncio.sleep(1)
    except Exception:
        pass
    pool = list(reversed(files))  # 同主图: 已有图=池前段, 倒着传新的
    idx = 0
    acted = False
    while True:
        c = await count_form_images(page)
        cur = int(c['detN'] or 0)
        if cur >= 10 or idx >= len(pool):
            break
        chunk = pool[idx:idx+5]
        idx += len(chunk)
        fis = det_sec.locator("input[type=file]")
        n = await fis.count()
        done_chunk = False
        for i in range(n):
            fi = fis.nth(i)
            try:
                mult = await fi.get_attribute('multiple')
                before = cur
                if mult is not None:
                    await fi.set_input_files(chunk, timeout=120000)
                    await asyncio.sleep(8)
                else:
                    for fpath in chunk:
                        await fi.set_input_files([fpath], timeout=60000)
                        await asyncio.sleep(2.5)
                acted = True
                c2 = await count_form_images(page)
                cur = int(c2['detN'] or 0)
                done_chunk = cur > before
                if done_chunk:
                    break
                # 没涨: 换下一个 input
            except Exception:
                continue
        if not done_chunk:
            break
    return acted, int((await count_form_images(page))['detN'] or 0) >= 10


FILL_FABRIC = """() => {
    const dd = document.querySelector('.aurora-dorami-composition-select-dropdown');
    if (!dd) return false;
    for (const item of dd.querySelectorAll('.aurora-select-item')) {
        if (item.getAttribute('title') === '聚酯纤维（涤纶）') { item.querySelector('.aurora-checkbox').click(); return true; }
    }
    return false;
}"""


async def fill_fabric(page):
    """面料材质修复 v4: 以「读 input 值」为准 —
    已有合法%行 → 删掉空%行(实测 remove 按钮有效); 全空 → 选聚酯纤维（涤纶）填100.
    每步验证, 失败返回 False(调用方标失败防空转)"""
    try:
        await page.locator('[data-kora="click_multi_value_measure_composition_select"]').first.click(timeout=5000)
        await asyncio.sleep(2)

        def _rows_js():
            return """() => {
                const list = document.querySelector('.aurora-dorami-composition-select-selected-list');
                if (!list) return [];
                return [...list.querySelectorAll('.aurora-dorami-composition-select-selected-row')].map(r => ({
                    text: (r.innerText||'').replace(/\\s+/g,''),
                    val: (r.querySelector('input')||{}).value || ''
                }));
            }"""

        rows = await page.evaluate(_rows_js())
        # 情形A: 已有行 → 删除空%行, 保留数字%行
        if rows:
            removed = await page.evaluate("""() => {
                const list = document.querySelector('.aurora-dorami-composition-select-selected-list');
                if (!list) return 0;
                let n = 0;
                for (const r of list.querySelectorAll('.aurora-dorami-composition-select-selected-row')) {
                    const inp = r.querySelector('input');
                    const v = (inp && inp.value || '').trim();
                    const ok = v && !isNaN(parseFloat(v)) && parseFloat(v) > 0;
                    if (!ok) {
                        const btn = r.querySelector('.aurora-dorami-composition-select-remove') ||
                                    r.querySelector('[class*=remove], [class*=close]');
                        if (btn) { btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); n++; }
                    }
                }
                return n;
            }""")
            await asyncio.sleep(1.5)
            rows = await page.evaluate(_rows_js())
            valid = [r for r in rows if r['val'] and r['val'].replace('.','').isdigit() and float(r['val']) > 0]
            if valid:
                # 有合法行: 补齐首行到100%(若不等)
                total = sum(float(r['val']) for r in valid)
                if abs(total - 100) > 0.5:
                    fixed = await page.evaluate("""() => {
                        const list = document.querySelector('.aurora-dorami-composition-select-selected-list');
                        const rows = list.querySelectorAll('.aurora-dorami-composition-select-selected-row');
                        const r = rows[0];
                        const inp = r.querySelector('input');
                        if (!inp) return false;
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(inp, '100');
                        inp.dispatchEvent(new Event('input', {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        inp.dispatchEvent(new Event('blur', {bubbles: true}));
                        return true;
                    }""")
                    await asyncio.sleep(1)
                rows = await page.evaluate(_rows_js())
                if all(r['val'] and float(r['val']) > 0 for r in rows) and rows:
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(1)
                    return True
                log(f"  ⚠ 填面料: 修复后仍异常({rows})")
                await page.keyboard.press('Escape')
                return False
            # 全是空%行 → 全删重来(情形B)
            await page.evaluate("""() => {
                const list = document.querySelector('.aurora-dorami-composition-select-selected-list');
                for (const r of list.querySelectorAll('.aurora-dorami-composition-select-selected-row')) {
                    const btn = r.querySelector('.aurora-dorami-composition-select-remove') ||
                                r.querySelector('[class*=remove], [class*=close]');
                    if (btn) btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                }
            }""")
            await asyncio.sleep(1.5)
        # 情形B: 无行(或已全删) → 搜索并勾选 聚酯纤维（涤纶）
        search = page.locator('.aurora-dorami-composition-select-dropdown input[placeholder="搜索材质"]')
        if await search.count() == 0:
            log("  ⚠ 填面料: 下拉/搜索框未找到")
            await page.keyboard.press('Escape')
            return False
        await search.click()
        await asyncio.sleep(0.3)
        await page.keyboard.type('聚酯纤维', delay=50)
        await asyncio.sleep(2)
        picked = await page.evaluate("""() => {
            const dd = document.querySelector('.aurora-dorami-composition-select-dropdown');
            if (!dd) return 'NO_DD';
            for (const item of dd.querySelectorAll('.aurora-select-item')) {
                if (item.getAttribute('title') === '聚酯纤维（涤纶）') {
                    const cb = item.querySelector('.aurora-checkbox');
                    if (!cb) return 'NO_CB';
                    const inp = cb.querySelector('input');
                    const checked = inp ? inp.checked : cb.className.includes('checked');
                    if (!checked) cb.click();
                    return 'OK';
                }
            }
            return 'NO_ITEM';
        }""")
        if picked != 'OK':
            log(f"  ⚠ 填面料: 选项定位失败({picked})")
            await page.keyboard.press('Escape')
            return False
        await asyncio.sleep(1.5)
        # 填百分比: 找 涤纶 行的 input, 原生 setter + 事件
        pct_ok = await page.evaluate("""() => {
            const list = document.querySelector('.aurora-dorami-composition-select-selected-list');
            if (!list) return 'NO_LIST';
            const rows = list.querySelectorAll('.aurora-dorami-composition-select-selected-row');
            let hit = null;
            for (const r of rows) { if ((r.innerText||'').includes('涤纶')) { hit = r; break; } }
            if (!hit) return 'NO_TARGET_ROW';
            const inp = hit.querySelector('input');
            if (!inp) return 'NO_INPUT';
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, '100');
            inp.dispatchEvent(new Event('input', {bubbles: true}));
            inp.dispatchEvent(new Event('change', {bubbles: true}));
            inp.dispatchEvent(new Event('blur', {bubbles: true}));
            return 'OK';
        }""")
        if pct_ok != 'OK':
            log(f"  ⚠ 填面料: 百分比定位失败({pct_ok})")
            await page.keyboard.press('Escape')
            return False
        await asyncio.sleep(1.5)
        rows = await page.evaluate(_rows_js())
        await page.keyboard.press('Escape')
        await asyncio.sleep(1)
        if rows and all(r['val'] and float(r['val']) > 0 for r in rows):
            return True
        log(f"  ⚠ 填面料: 最终验证未通过({rows})")
        return False
    except Exception as e:
        log(f"  ⚠ 填面料异常: {str(e)[:60]}")
        try:
            await page.keyboard.press('Escape')
        except Exception:
            pass
        return False


async def has_fabric_error(page):
    return await page.evaluate("""() => {
        const errs = document.querySelectorAll('.ecom-g-form-item-has-error, [class*="form-item-has-error"], [class*="error-tip"]');
        for (const e of errs) {
            if (e.offsetParent && /面料材质|该项为必填/.test(e.innerText||'')) return true;
        }
        return false;
    }""")


async def publish(page):
    """点发布商品→弹窗链→以保存API响应为准判定 (编辑走审核: audit_pass=false 也算保存成功)"""
    saved_result = [None]

    async def on_resp(r):
        u = r.url
        if ('editWithSchema' in u) or ('createWithSchema' in u) or ('tproduct/save' in u):
            try:
                body = await r.json()
                if (body.get('errno') == 0 and body.get('code') == 0) or body.get('st') == 0:
                    d = body.get('data') or {}
                    saved_result[0] = f"saved(审核={'通过' if d.get('audit_pass') else '提交'})"
                else:
                    saved_result[0] = f"API错误: {str(body.get('message') or body.get('msg'))[:60]}"
            except Exception:
                pass

    page.on('response', on_resp)
    try:
        btn = page.locator("button:has-text('发布商品')").last
        await btn.scroll_into_view_if_needed(timeout=8000)
        await btn.click(timeout=8000)
    except Exception:
        try:
            await page.evaluate("""() => {
                const btn = [...document.querySelectorAll('button')]
                    .find(b => (b.innerText || '').trim() === '发布商品');
                if (btn) btn.click();
            }""")
        except Exception:
            page.remove_listener('response', on_resp)
            return False, '发布按钮点不到'
    for round_i in range(24):
        await asyncio.sleep(3.5)
        if saved_result[0]:
            ok = saved_result[0].startswith('saved')
            page.remove_listener('response', on_resp)
            return ok, saved_result[0]
        st = await page.evaluate("""() => {
            const t = document.body.innerText || '';
            if (location.href.includes('success.htm')) return {k:'ok'};
            if (/线上商品数据已更新|商品发布成功|提交成功/.test(t)) return {k:'ok'};
            if (/被挤爆啦/.test(t)) return {k:'busy'};
            const errs = document.querySelectorAll('.ecom-g-form-item-has-error, [class*="form-item-has-error"], [class*="error-tip"]');
            const out = [];
            for (const e of errs) {
                if (e.offsetParent) out.push((e.innerText||'').trim().replace(/\s+/g,' ').slice(0,50));
            }
            if (out.length) return {k:'validation', detail: [...new Set(out)].slice(0,4).join(' | ')};
            return {k:''};
        }""")
        if st['k'] == 'ok':
            page.remove_listener('response', on_resp)
            return True, '发布成功'
        if st['k'] == 'validation':
            d = st.get('detail', '')
            page.remove_listener('response', on_resp)
            if '类目' in d and ('填写有误' in d or '未开通' in d):
                return False, 'CATBLOCK:' + d[:80]
            return False, f'表单校验错误: {d}'
        if st['k'] == 'busy':
            await asyncio.sleep(10)
            continue
        try:
            acted = await page.evaluate("""() => {
                const bs = [...document.querySelectorAll('button')].filter(b => b.offsetParent);
                const dlg = [...document.querySelectorAll('.ecom-g-modal, .ant-modal, [class*="modal"]')]
                    .find(m => m.offsetParent);
                if (!dlg) return null;
                for (const re of [/不修改，继续发布/, /继续发布/, /推荐有误/, /确认发布/, /确定/, /我知道了/]) {
                    const b = bs.find(x => re.test((x.innerText||'').trim()));
                    if (b) { b.click(); return (b.innerText||'').trim(); }
                }
                return null;
            }""")
            if acted:
                log(f"  · 弹窗: {acted}")
        except Exception:
            pass
    page.remove_listener('response', on_resp)
    return False, '未确认发布成功(无保存响应)'


async def wait_hydrated(page, max_s=45):
    """等编辑页主图区水合稳定: file input≥5 且连续两次计数不变"""
    last = None
    waited = 0
    while waited < max_s:
        c = await count_form_images(page)
        key = (c['mainN'], c['mainFI'], c['detN'])
        if c['mainFI'] and c['mainFI'] >= 5 and key == last:
            return c
        last = key
        await asyncio.sleep(3)
        waited += 3
    return await count_form_images(page)


async def process_one(ctx, oid, rec, pid, page):
    """编辑一个商品补图, 返回 (ok, msg)"""
    mains = [p for p in (rec.get('main_imgs') or []) if os.path.exists(p)][:5]
    dets = [p for p in (rec.get('detail_imgs') or []) if os.path.exists(p)][:15]
    if len(mains) < 5 or len(dets) < 10:
        return False, f'数据仍不足 主{len(mains)} 详{len(dets)}'

    await page.goto(EDIT_URL.format(pid=pid), wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(10000)
    if 'login' in page.url or 'passport' in page.url:
        return False, '登录态失效'

    if not await delete_draft_if_any(page):
        return False, '删草稿失败'

    cnt = await wait_hydrated(page)
    log(f"  现状: 主图{cnt['mainN']} 详情{cnt['detN']} (水合稳定)")
    if int(cnt['mainN'] or 0) >= 5 and int(cnt['detN'] or 0) >= 10:
        return True, '本就达标, 无需处理'

    # 补主图
    need_main = max(0, 5 - int(cnt['mainN'] or 0))
    uploaded_main = 0
    if need_main > 0:
        uploaded_main = await upload_main_imgs(page, mains, need_main)
        await asyncio.sleep(3)

    # 补详情图
    uploaded_det = False
    det_ok = False
    if int(cnt['detN'] or 0) < 10:
        uploaded_det, det_ok = await upload_detail_imgs(page, dets, int(cnt['detN'] or 0))
        await asyncio.sleep(5)

    cnt2 = await count_form_images(page)
    log(f"  补后: 主图{cnt2['mainN']}(+{uploaded_main}) 详情{cnt2['detN']}")
    if int(cnt2['mainN'] or 0) < 5 and uploaded_main == 0:
        return 'SRCLIMIT', f'主图{cnt2["mainN"]}张: 源图池无新内容(去重后不足)'
    if int(cnt2['detN'] or 0) < 10:
        return False, f'详情图补后仍不足({cnt2["detN"]})'

    # 面料材质必填: 编辑页常为空, 先补(失败则本件标失败, 防空转)
    if await has_fabric_error(page):
        log("  · 面料材质为空, 补聚酯纤维100%")
        if not await fill_fabric(page):
            return False, '面料材质填写失败'

    ok, msg = await publish(page)
    if not ok and '校验' in msg:
        if not await fill_fabric(page):
            return False, f'面料材质二次填写失败: {msg}'
        ok, msg = await publish(page)
    return ok, msg


async def main():
    args = sys.argv[1:]
    test = '--test' in args
    limit = int(args[args.index('--limit') + 1]) if '--limit' in args else 0
    force_oid = args[args.index('--oid') + 1] if '--oid' in args else None
    if '--retry-failed' in args:
        prog0 = load_json(PROGRESS, {"done": [], "failed": [], "nomatch": []})
        uniq = []
        seen = set()
        for f in prog0['failed']:
            oid = f['offerId'] if isinstance(f, dict) else f
            if oid not in seen:
                seen.add(oid)
                uniq.append(f)
        with open(PROGRESS + '.failed.bak', 'w', encoding='utf-8') as f:
            json.dump(prog0['failed'], f, ensure_ascii=False, indent=1)
        prog0['failed'] = []
        save_progress(prog0)
        log(f"--retry-failed: 清空失败队列 {len(uniq)} 个(去重后), 备份至 .failed.bak")

    prog = load_json(PROGRESS, {"done": [], "failed": [], "nomatch": []})
    done_set = set(prog['done'])

    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()

        # 店铺标题→pid 映射 (启动时建一次, 后续每轮重建)
        store_map = await fetch_store_map(page)
        log(f"店铺列表映射: {len(store_map)} 条")

        idle_rounds = 0
        while True:
            done_set = set(prog['done'])  # 每轮刷新, 防止死循环重处理
            created = set(load_json(CREATE_PROGRESS, {}).get('created', {}).keys())
            fix_done = set(load_json(FIX_SCRAPE_PROGRESS, {}).get('done', []))
            dm = {r.get('offerId'): r.get('product_id') for r in load_json(DRAFT_MATCH, []) if r.get('offerId')}
            data = {}
            order = []
            with open(DATA, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            r = json.loads(line)
                            data[str(r['offerId'])] = r
                            order.append(str(r['offerId']))
                        except Exception:
                            pass

            todo = []
            catblocked = set(prog.get('catblocked', []))
            srclimit = set(prog.get('srclimit', []))
            for oid in order:
                if oid in done_set or oid in prog['failed'] or oid in prog['nomatch'] or oid in catblocked or oid in srclimit:
                    continue
                if oid not in created:
                    continue
                if oid not in fix_done:
                    continue  # 补采还没跑到
                rec = data.get(oid)
                if not rec:
                    continue
                mains = [x for x in (rec.get('main_imgs') or []) if os.path.exists(x)]
                dets = [x for x in (rec.get('detail_imgs') or []) if os.path.exists(x)]
                if len(mains) < 5 or len(dets) < 10:
                    continue
                pid = dm.get(oid) or store_map.get(re.sub(r'\s+', '', compute_title(rec))[:10])
                if not pid:
                    prog['nomatch'].append(oid)
                    save_progress(prog)
                    continue
                todo.append((oid, pid, rec))

            if limit and len(done_set) >= limit:
                log("达到 --limit, 退出")
                break

            if not todo:
                idle_rounds += 1
                if test:
                    log("TEST: 无可处理项, 退出")
                    break
                if idle_rounds >= 40:  # ~20分钟无新任务视为补采已完成/无任务
                    log("连续20分钟无可处理项, 退出")
                    break
                log(f"暂无可处理项, 等 30s (第{idle_rounds}轮)")
                await asyncio.sleep(30)
                continue
            idle_rounds = 0

            if force_oid:
                cand = [x for x in todo if x[0] == force_oid]
                if not cand:
                    log(f"TEST: 指定 --oid {force_oid} 不在可处理列表, 退出")
                    break
                oid, pid, rec = cand[0]
            else:
                oid, pid, rec = todo[0]
            log(f"[{len(done_set)+1}] {oid} → product {pid}")
            try:
                ok, msg = await process_one(ctx, oid, rec, pid, page)
            except Exception as e:
                ok, msg = False, f'异常: {str(e)[:80]}'
            if ok:
                prog['done'].append(oid)
                log(f"  ✓ {msg}")
            elif msg == 'SRCLIMIT' or msg.startswith('SRCLIMIT'):
                prog.setdefault('srclimit', []).append(oid)
                log(f"  ○ 源图上限: {msg[9:60]}")
            elif msg.startswith('CATBLOCK'):
                prog.setdefault('catblocked', []).append(oid)
                log(f"  ⛔ 类目阻塞(建议情趣内衣未开通), 转重建队列: {msg[9:60]}")
            else:
                prog['failed'].append({"offerId": oid, "err": msg})
                log(f"  ✗ {msg}")
                # 连续失败保护
                recent_fails = prog['failed'][-5:]
                if len(recent_fails) == 5 and all(isinstance(x, dict) for x in recent_fails):
                    log("  连续失败较多, 冷却 120s")
                    await asyncio.sleep(120)
            save_progress(prog)
            await asyncio.sleep(random.uniform(28, 40))
            if test:
                log("TEST: 处理1个即退出")
                break

        try:
            await page.close()
        except Exception:
            pass
        await b.close()
    log(f"结束: done={len(prog['done'])} failed={len(prog['failed'])} nomatch={len(prog['nomatch'])}")


asyncio.run(main())
