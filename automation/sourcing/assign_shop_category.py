#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""淘宝仓库商品批量归类「店铺中分类」 (9222, item.upload 编辑页)

流程(每商品新开 tab, 用完只关自己的 tab):
  1. 打开编辑页 item.upload.taobao.com/sell/v2/publish.htm?itemId={id}
  2. 等页面加载 → 滚动水合 → 校验上架时间=放入仓库(防误上架)
  3. 若「提取方式」未选第一个"使用物流配送" → 选之
  4. 展开店铺中分类树 → 清空已勾选 → 勾目标类目 checkbox → 收起 → 校验 .next-tag 显示目标
  5. 点「提交宝贝信息」→ 以网络响应/页面"提交成功"判定成功(页面文本不可靠)

用法:
  python assign_shop_category.py --test             # 只处理1个
  python assign_shop_category.py --limit N
  python assign_shop_category.py --start N          # 从第N个开始
进度: shop_cat_progress.json (done/failed/skipped)
"""
import asyncio
import fcntl
import json
import os
import random
import re
import sys
import time
import traceback
from playwright.async_api import async_playwright
from cdp_utils import connect_cdp

CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
PLAN_FILE = os.path.join(BASE, "shop_cat_plan.json")
PROGRESS_FILE = os.path.join(BASE, "shop_cat_progress.json")
EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"
CATS = ['家居服/睡衣', '牛仔短裤', '秋冬款', '连衣裙', '长裤', '半身裙', '美甲', 'other']


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_plan():
    return json.load(open(PLAN_FILE, encoding='utf-8'))


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            return json.load(open(PROGRESS_FILE, encoding='utf-8'))
        except Exception:
            pass
    return {"done": [], "failed": {}, "skipped": []}


def save_progress(prog):
    lock_fd = open(PROGRESS_FILE + '.lock', 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        # 多 worker 并行时: 先读盘上最新进度, 合并后再写, 避免互相覆盖
        disk = load_progress()
        disk_done = set(disk['done']) | set(prog['done'])
        disk_skipped = set(disk['skipped']) | set(prog['skipped'])
        disk_failed = dict(disk['failed'])
        disk_failed.update(prog['failed'])
        merged = {"done": sorted(disk_done), "failed": disk_failed, "skipped": sorted(disk_skipped)}
        json.dump(merged, open(PROGRESS_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


async def handle_recommend_dialog(page):
    """处理编辑页弹出的「商品属性信息更新确定」确认框 (系统推荐属性), 可能连弹多个.
    用户要求: 弹框出现必须点「确定」确认. 用 Playwright 真实点击(JS .click 对 React 不可靠).
    处理: 循环检测弹框(最多15s) → 点「确定」→ 直到无弹框. 返回 (handled, msg)"""
    confirmed = 0
    for _ in range(5):
        # 等弹框出现(最多15s)
        has = False
        for _ in range(15):
            has = await page.evaluate("""() => {
                return [...document.querySelectorAll('.next-dialog')].some(e =>
                    e.getClientRects().length > 0 && (e.innerText||'').includes('属性信息更新'));
            }""")
            if has:
                break
            await asyncio.sleep(1)
        if not has:
            break
        await asyncio.sleep(0.8)
        # 用 Playwright 真实点击「确定」(在属性弹框内, 排除其他区域)
        clicked = False
        dlg = page.locator('.next-dialog', has_text='属性信息更新').last
        try:
            btn = dlg.locator('button', has_text='确定').last
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=4000, force=True)
                clicked = True
        except Exception:
            pass
        if not clicked:
            # 兜底: JS 点击确定
            await page.evaluate("""() => {
                const d = [...document.querySelectorAll('.next-dialog')].find(e =>
                    e.getClientRects().length > 0 && (e.innerText||'').includes('属性信息更新'));
                if (!d) return;
                const bs = [...d.querySelectorAll('button')];
                for (const b of bs) {
                    if ((b.textContent||'').trim() === '确定') { b.click(); return; }
                }
            }""")
        confirmed += 1
        await asyncio.sleep(1.5)
    if confirmed > 0:
        return True, f'已点确定确认{confirmed}次属性推荐弹框'
    return False, '无弹框'


async def wait_edit_ready(page, timeout=90):
    """等编辑页标题输入框出现(表示表单已水合)"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        title = await page.evaluate("""() => {
            const inp = document.querySelector('#sell-field-title input, input[placeholder*="标题"], input[name*="title"]');
            return inp && inp.value ? inp.value : '';
        }""")
        if title:
            return title
        await asyncio.sleep(2)
    return None


async def scroll_edit_page(page):
    for y in range(0, 7001, 1500):
        await page.evaluate(f"window.scrollTo(0, {y})")
        await asyncio.sleep(0.3)


async def check_listing_mode(page):
    """确认上架时间=放入仓库. 返回 (ok, current_text)"""
    r = await page.evaluate("""() => {
        const el = document.querySelector('#sell-field-startTime');
        if (!el) return {ok:false, txt:'NO_FIELD'};
        const wrappers = el.querySelectorAll('.next-radio-wrapper, .radio-item');
        for (const w of wrappers) {
            const checked = w.getAttribute('aria-checked')==='true' || w.classList.contains('checked') || (w.querySelector('input')||{}).checked;
            const t = (w.textContent||'').trim();
            if (checked) return {ok: true, txt: t.slice(0,20)};
        }
        return {ok:false, txt:'NONE_SELECTED'};
    }""")
    return r


async def ensure_extract_way(page):
    """提取方式: 若 '使用物流配送' 未选中则选第一个选项. 返回 (ok, msg)"""
    r = await page.evaluate("""() => {
        const el = document.querySelector('#sell-field-tbExtractWay, [id*="ExtractWay"]');
        if (!el) return {ok:true, msg:'FIELD_NOT_FOUND'};
        const radios = el.querySelectorAll('label, .radio-item, .next-radio-wrapper');
        let checkedText = null;
        for (const l of radios) {
            const t = (l.textContent||'').trim().replace(/\\s+/g,' ').slice(0,20);
            const r = l.querySelector('input');
            const checked = r ? r.checked : (l.getAttribute('aria-checked')==='true' || l.classList.contains('checked'));
            if (checked && t) checkedText = t;
        }
        if (checkedText) return {ok:true, msg:'ALREADY: '+checkedText};
        // 未选 → 点第一个选项
        for (const l of radios) {
            const t = (l.textContent||'').trim().replace(/\\s+/g,' ').slice(0,20);
            if (t) { l.click(); return {ok:true, msg:'CLICKED: '+t}; }
        }
        return {ok:false, msg:'NO_OPTION'};
    }""")
    await asyncio.sleep(0.5)
    return r.get('ok', False), r.get('msg', '')


async def set_shop_category(page, target):
    """设置店铺中分类: 清空已勾选 → 勾目标类目. 返回 (ok, msg)"""
    # 展开
    ok = await page.evaluate("""() => {
        const t = document.querySelector('#sell-field-shopcat .next-select-trigger');
        if (t) { t.click(); return true; }
        return false;
    }""")
    if not ok:
        return False, '店铺中分类触发点未找到'
    await asyncio.sleep(2.5)
    # 树节点
    nodes = await page.evaluate("""() => {
        return [...document.querySelectorAll('.next-overlay-inner .next-tree-node')].map(n => {
            const label = n.querySelector('.next-tree-node-label, .next-tree-node-title');
            const cb = n.querySelector('.next-checkbox-wrapper');
            return {
                text: (label||n).textContent.trim(),
                cb,
                checked: cb ? (cb.classList.contains('checked') || cb.getAttribute('aria-checked')==='true') : false
            };
        });
    }""")
    if not nodes:
        await page.keyboard.press('Escape')
        return False, '树节点为空'
    # 清空已勾选
    cleared = await page.evaluate("""(target) => {
        const nodes = document.querySelectorAll('.next-overlay-inner .next-tree-node');
        let n = 0;
        for (const nd of nodes) {
            const label = nd.querySelector('.next-tree-node-label, .next-tree-node-title');
            const cb = nd.querySelector('.next-checkbox-wrapper');
            const text = (label||nd).textContent.trim();
            if (cb && text !== target && (cb.classList.contains('checked') || cb.getAttribute('aria-checked')==='true')) {
                cb.click(); n++;
            }
        }
        return n;
    }""", target)
    if cleared:
        await asyncio.sleep(1.2)
    # 勾目标
    clicked = await page.evaluate("""(target) => {
        const nodes = document.querySelectorAll('.next-overlay-inner .next-tree-node');
        for (const nd of nodes) {
            const label = nd.querySelector('.next-tree-node-label, .next-tree-node-title');
            const cb = nd.querySelector('.next-checkbox-wrapper');
            const text = (label||nd).textContent.trim();
            if (text === target) {
                if (cb.classList.contains('checked') || cb.getAttribute('aria-checked')==='true') return 'ALREADY';
                cb.click();
                return 'CLICKED';
            }
        }
        return 'NOT_FOUND';
    }""", target)
    if clicked == 'NOT_FOUND':
        await page.keyboard.press('Escape')
        return False, f'目标类目[{target}]不在树中'
    await asyncio.sleep(1.5)
    # 收起
    await page.keyboard.press('Escape')
    await asyncio.sleep(1)
    # 校验已选
    sel = await page.evaluate("""() => {
        const tags = document.querySelectorAll('#sell-field-shopcat .next-tag');
        return Array.from(tags).map(t=>t.textContent.trim());
    }""")
    if target in sel:
        return True, '选中: ' + ','.join(sel)
    return False, f'校验失败, 当前已选: {sel}'


async def clear_size_table(page):
    """清空「商品尺寸表」: 定位 #sell-field-sizeMapping → 点「一键清空」→ 确认.
    尺码表要么全填要么不填, 部分填写会报 CHK_SIZE_ROW_IS_EMPTY. 返回 (ok, msg)"""
    # 先滚动让尺寸表区域渲染
    for y in range(0, 7001, 1500):
        await page.evaluate(f"window.scrollTo(0, {y})")
        await asyncio.sleep(0.2)
    # 定位 商品尺寸表 wrapper (固定 id #sell-field-sizeMapping)
    wrapper_id = await page.evaluate("""() => {
        const w = document.getElementById('sell-field-sizeMapping');
        if (w) return 'sell-field-sizeMapping';
        // 兜底: 按 label 文本查找
        const lab = [...document.querySelectorAll('*')].find(e =>
            e.children.length===0 && (e.innerText||'').trim()==='商品尺寸表');
        if (!lab) return null;
        let c = lab;
        for (let i=0;i<8;i++){ c=c.parentElement; if(!c) break;
            if (c.id && c.id.includes('sizeMapping')) return c.id; }
        return null;
    }""")
    if not wrapper_id:
        return False, '商品尺寸表区域未找到'
    # 点「一键清空」
    clicked = await page.evaluate("""(wid) => {
        const w = document.getElementById(wid);
        if (!w) return false;
        const bs = [...w.querySelectorAll('button')];
        for (const b of bs) {
            if ((b.textContent||'').trim() === '一键清空') { b.click(); return true; }
        }
        // 兜底: 全页范围找一键清空(确保是尺寸表区域的)
        const all = [...document.querySelectorAll('.sell-component-size-mapping button, [id*="sizeMapping"] button')];
        for (const b of all) {
            if ((b.textContent||'').trim() === '一键清空') { b.click(); return true; }
        }
        return false;
    }""", wrapper_id)
    if not clicked:
        return False, '未找到一键清空按钮'
    await asyncio.sleep(1.5)
    # 可能的确认弹框("确认清空?")
    await page.evaluate("""() => {
        const bs = [...document.querySelectorAll('button')].filter(b => b.offsetParent);
        for (const b of bs) {
            const t = (b.textContent||'').trim();
            if (t === '确定' || t === '确认' || t === '清空') { b.click(); return; }
        }
    }""")
    await asyncio.sleep(1.5)
    return True, '已清空商品尺寸表'


async def click_submit(page):
    """提交宝贝信息, 以 submit.htm 响应驱动判定成功/失败/数据问题.
    机制(实测):
      提交 → 服务器返回模型(globalMessage):
        - type=success → 成功(跳转 success.htm)
        - warning + 违规弹窗(尺寸表) → 按钮「继续发布」/「前往查看」→ 点按钮后
          有的直接成功, 有的需再次点提交 → 继续监听下一次 submit 响应
        - error + formError(CHK_SIZE_ROW_IS_EMPTY) → 数据问题(尺寸表行未填) → 标 failed
    返回 (ok, msg, risk): ok=True 成功 / risk=True 风控(冷却重试) / ok=False 数据问题
    """
    submit_bodies = []

    async def _on_resp(resp):
        try:
            if 'submit' in resp.url and 'item.upload' in resp.url and 'gm.mmstat' not in resp.url:
                try:
                    body = await resp.text()
                except Exception:
                    body = ''
                submit_bodies.append((resp.status, body))
        except Exception:
            pass
    page.on('response', _on_resp)

    def _click_submit_btn():
        return page.evaluate("""() => {
            const bs = [...document.querySelectorAll('button')].filter(b => b.offsetParent);
            for (const b of bs) {
                if ((b.textContent||'').trim() === '提交宝贝信息') { b.click(); return true; }
            }
            return false;
        }""")

    def _click_btn(label):
        return page.evaluate("""(t) => {
            const bs = [...document.querySelectorAll('button')].filter(b => b.offsetParent);
            for (const b of bs) {
                if ((b.textContent||'').trim() === t) { b.click(); return true; }
            }
            return false;
        }""", label)

    async def _check_response():
        """检查最近的 submit 响应体, 返回 ('success'|'error_size'|'error_data'|'warning'|'none', msg)"""
        for st, body in reversed(submit_bodies):
            if 'RGV587' in body or 'FAIL_SYS_USER_VALIDATE' in body:
                return 'risk', 'RGV587风控拦截提交(punish)'
            if not body or 'globalMessage' not in body:
                continue
            if '"success"' in body and 'globalMessage' in body:
                return 'success', '提交成功(响应确认)'
            if '"error"' in body or 'formError' in body:
                if 'CHK_SIZE_ROW_IS_EMPTY' in body or 'sizeMapping' in body:
                    return 'error_size', '商品尺寸表行未填写'
                return 'error_data', body[:150]
            if 'warning' in body:
                return 'warning', body[:150]
        return 'none', ''

    # 1. 点提交
    await _click_submit_btn()

    # 2. 响应驱动循环(最多8轮)
    size_cleared = False
    for round_ in range(8):
        await asyncio.sleep(3)
        if await _detect_risk(page):
            return False, '风控/验证码', True
        # 属性推荐弹框: 出现则点确定(用户要求必须确认)
        attr_dlg = await page.evaluate("""() => {
            return [...document.querySelectorAll('.next-dialog')].some(e =>
                e.getClientRects().length > 0 && (e.innerText||'').includes('属性信息更新'));
        }""")
        if attr_dlg:
            try:
                dlg = page.locator('.next-dialog', has_text='属性信息更新').last
                btn = dlg.locator('button', has_text='确定').last
                await btn.click(timeout=4000, force=True)
            except Exception:
                await _click_btn('确定')
            await asyncio.sleep(1.5)
            continue
        # 「我知道了」提示弹窗(2026-09-18 实测): 会挡住提交流程, 必须点掉才有真实提交响应
        if await _click_btn('我知道了'):
            await asyncio.sleep(2)
            continue
        # 成功页直接判定
        if 'success.htm' in page.url:
            return True, '提交成功(跳转成功页)', False
        # 响应体判定
        kind, msg = await _check_response()
        if kind == 'risk':
            return False, msg, True
        if kind == 'success':
            return True, msg, False
        if kind == 'error_size':
            # 商品尺寸表行未填: 清空尺寸表后重新提交(尺码表要么全填要么不填)
            if not size_cleared:
                ok, cmsg = await clear_size_table(page)
                if ok:
                    log(f"  · {cmsg}, 重新提交")
                    size_cleared = True
                    submit_bodies.clear()
                    await _click_submit_btn()
                    continue
                return False, f'尺寸表清空失败: {cmsg}', False
            return False, f'数据问题: {msg}', False
        if kind == 'error_data':
            return False, f'数据问题: {msg}', False
        # 违规弹窗(尺寸表)
        pop = await page.evaluate("""() => {
            const bs = [...document.querySelectorAll('button')].filter(b => b.offsetParent).map(b=>(b.textContent||'').trim());
            const ds = [...document.querySelectorAll('.next-dialog-body, .next-overlay-inner')].filter(e=>e.offsetParent);
            if (ds.length && ds.some(d => /违规|尺寸表|尺码/.test(d.innerText||''))) {
                if (bs.includes('继续发布')) return 'CONTINUE';
                if (bs.includes('前往查看')) return 'GOTO_VIEW';
            }
            return null;
        }""")
        if pop == 'CONTINUE':
            await _click_btn('继续发布')
            await asyncio.sleep(3)
            # 继续发布后多数直接成功; 若仍在编辑页且无新弹窗, 再点提交
            if 'publish.htm' in page.url and not await _is_success(page):
                await _click_submit_btn()
            continue
        elif pop == 'GOTO_VIEW':
            await _click_btn('前往查看')
            await asyncio.sleep(3)
            # 前往查看后部分直接成功; 若仍在编辑页且无新弹窗/新响应, 再点提交
            if 'publish.htm' in page.url and not await _is_success(page):
                # 只有没有新的成功响应时才再提交
                kind2, _ = await _check_response()
                if kind2 != 'success':
                    await _click_submit_btn()
            continue
        else:
            # 无弹窗: 数据校验错误? / 仍在编辑页 → 再点一次提交
            ferr = await page.evaluate("""() => {
                const t = document.body.innerText || '';
                for (const k of ['尚未填写', '填写错误', '校验不通过', '必填字段', '不能为空', '请填写']) {
                    if (t.includes(k)) return t.slice(0, 100);
                }
                return null;
            }""")
            if ferr:
                # 商品尺寸表未填: 清空后重提交(尺码表要么全填要么不填)
                if ('商品尺寸表' in ferr or '尺寸表' in ferr) and not size_cleared:
                    ok, cmsg = await clear_size_table(page)
                    if ok:
                        log(f"  · {cmsg}, 重新提交")
                        size_cleared = True
                        submit_bodies.clear()
                        await _click_submit_btn()
                        continue
                    return False, f'尺寸表清空失败: {cmsg}', False
                return False, f'数据问题: {ferr}', False
            if 'publish.htm' in page.url:
                await _click_submit_btn()
                await asyncio.sleep(2)
                continue
            return False, '提交后停留未知页面', False

    if await _is_success(page):
        return True, '提交成功', False
    return False, '提交超时未确认', False


async def _is_success(page):
    url = page.url
    if 'success.htm' in url:
        return True
    st = await page.evaluate("""() => {
        const t = document.body.innerText || '';
        return /商品提交成功|提交成功/.test(t);
    }""")
    return bool(st)


async def _detect_risk(page):
    """检测滑块/验证码/被挤爆"""
    r = await page.evaluate(r"""() => {
        for (const s of ['#nc_1_wrapper', '.nc_iconfont', '#aliyunCaptcha', '.baxia-dialog',
                         '.nc-container', '[class*="captcha"]', '[class*="verify"]']) {
            const el = document.querySelector(s);
            if (el && el.offsetParent) {
                const r = el.getBoundingClientRect();
                if (r.width > 150 && r.height > 30) return true;
            }
        }
        const t = document.body.innerText || '';
        if (/被挤爆啦|操作频繁|验证码错误/.test(t)) return true;
        return false;
    }""")
    return bool(r)


async def process_one(ctx, rec):
    """处理单个商品. 返回 (status, msg). status: ok/fail/risk"""
    item_id = rec['itemId']
    category = rec['category']
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), timeout=60000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page)
        if not title:
            return 'fail', '页面加载超时(表单未水合)'
        # 处理「商品属性信息更新确定」推荐属性弹框(必须点确定, 可能滚动时再触发)
        rh, rmsg = await handle_recommend_dialog(page)
        if rh:
            log(f"  · {rmsg}")
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        # 滚动后可能触发弹框, 再确认一次
        rh2, rmsg2 = await handle_recommend_dialog(page)
        if rh2:
            log(f"  · {rmsg2}")
        # 校验上架时间
        lm = await check_listing_mode(page)
        if not lm.get('ok') or '放入仓库' not in lm.get('txt', ''):
            return 'fail', f'上架时间非放入仓库: {lm.get("txt")}'
        # 提取方式
        eok, emsg = await ensure_extract_way(page)
        # 店铺中分类
        cok, cmsg = await set_shop_category(page, category)
        if not cok:
            return 'fail', f'类目设置失败: {cmsg}'
        # 提交前再确认无属性弹框遮挡
        rh3, rmsg3 = await handle_recommend_dialog(page)
        if rh3:
            log(f"  · {rmsg3}")
        # 提交
        sok, smsg, risk = await click_submit(page)
        if risk:
            return 'risk', f'{smsg}'
        if not sok:
            return 'fail', f'提交失败: {smsg}'
        return 'ok', f'{category} | {smsg}'
    except Exception as e:
        estr = str(e)
        if 'closed' in estr or 'crash' in estr.lower() or 'Target' in estr:
            return 'risk', '页面已失效: ' + estr[:60]
        return 'fail', estr[:80]
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def cleanup_leaked_tabs(ctx, my_ids):
    """治本: 每处理完一个商品回收本任务泄漏的孤儿 tab, 防内存/标签堆积.

    背景: 提交成功后 success.htm 会弹 1-2 个子窗口(xdomain-storage 跨域存储),
    page.close() 管不到子窗; 商品驱动崩溃时 tab 直接残留. 多商品累积吃内存.
    规则(只动本 worker 分片 + 纯泄漏页, 绝不动另一 worker 正在用的 tab):
      - xstore.insights.1688.com: 提交成功页/编辑页带出的 1688 数据页, 纯泄漏直接关
      - URL 含 itemId=/primaryId= 且该 itemId ∈ my_ids(本 worker 分片的 todo): 关
        (上一商品已提交/超时, 其间残留的 success.htm/publish.htm/xdomain 子窗全回收;
         另一 worker 的 tab 因 itemId 不在本集合被保留)
    ⚠️ 勿用 plan 索引推断分片 —— worker 分片是"过滤后 todo"的索引, 与 plan 索引不一致,
    用 plan 索引会误关另一 worker 正在用的 tab (2026-08-30 已踩坑).
    """
    try:
        closed = 0
        for pg in list(ctx.pages):
            try:
                u = pg.url
                if 'xstore.insights.1688.com' in u:
                    await pg.close()
                    closed += 1
                    continue
                m = re.search(r'(?:itemId|primaryId)=(\d+)', u)
                if m and m.group(1) in my_ids:
                    await pg.close()
                    closed += 1
            except Exception:
                pass
        if closed:
            log(f"  · 回收泄漏 tab {closed} 个")
    except Exception:
        pass


async def main():
    test = '--test' in sys.argv
    limit = 0
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    start = 0
    if '--start' in sys.argv:
        start = int(sys.argv[sys.argv.index('--start') + 1])
    worker_k = 0
    worker_n = 1
    if '--worker' in sys.argv:
        worker_k = int(sys.argv[sys.argv.index('--worker') + 1])
        worker_n = int(sys.argv[sys.argv.index('--worker') + 2])

    plan = load_plan()
    prog = load_progress()
    done = set(prog['done'])
    skipped = set(prog['skipped'])
    failed_ids = set(prog['failed'].keys())
    retry_failed = '--retry-failed' in sys.argv

    todo = [r for r in plan[start:] if r['itemId'] not in done and r['itemId'] not in skipped
            and (retry_failed or r['itemId'] not in failed_ids)]
    if worker_n > 1:
        todo = [r for i, r in enumerate(todo) if i % worker_n == worker_k]
    my_ids = {str(r['itemId']) for r in todo}
    if test:
        todo = todo[:1]
    elif limit:
        todo = todo[:limit]
    log(f"计划 {len(plan)} 个, 已完成 {len(done)}, 跳过 {len(skipped)}, 失败(待人工) {len(failed_ids)}, 本次处理 {len(todo)} (worker {worker_k}/{worker_n})")

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)

    ok_c = fail_c = risk_c = 0
    for i, rec in enumerate(todo):
        item_id = rec['itemId']
        category = rec['category']
        t0 = time.time()
        log(f"[{i+1}/{len(todo)}] {item_id} -> {category} ...")
        try:
            status, msg = await asyncio.wait_for(process_one(ctx, rec), timeout=120)
            if status == 'ok':
                ok_c += 1
                prog['done'].append(item_id)
                log(f"  ✓ {msg} ({round(time.time()-t0)}s)")
            elif status == 'risk':
                risk_c += 1
                log(f"  ⚠ 风控: {msg}")
            else:
                fail_c += 1
                prog['failed'][item_id] = {'category': category, 'error': msg}
                log(f"  ✗ {msg}")
        except asyncio.TimeoutError:
            fail_c += 1
            prog['failed'][item_id] = {'category': category, 'error': '处理超时120s(可能已提交, 待重试)'}
            log(f"  ✗ 处理超时120s(可能已提交), 继续下一个")
        except Exception as e:
            fail_c += 1
            prog['failed'][item_id] = {'category': category, 'error': str(e)[:80]}
            log(f"  ✗ 异常: {str(e)[:80]}")
        save_progress(prog)
        # 治本: 回收本 worker 分片泄漏的孤儿 tab(success.htm 子窗 / 崩溃残留), 防内存堆积
        await cleanup_leaked_tabs(ctx, my_ids)
        # 节奏控制
        if status == 'risk':
            log("  风控, 冷却600s...")
            await asyncio.sleep(600)
        else:
            await asyncio.sleep(random.uniform(3, 5))
        if (i + 1) % 30 == 0:
            rest = random.uniform(25, 35)
            log(f"  已处理 {i+1}, 休息 {int(rest)}s 防风控...")
            await asyncio.sleep(rest)
        if test:
            break

    log(f"完成: 本次成功={ok_c} 失败={fail_c} 风控={risk_c}, 累计 done={len(prog['done'])}")
    await b.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log('手动中断')
    except Exception:
        traceback.print_exc()
