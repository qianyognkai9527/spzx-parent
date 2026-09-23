"""fix_scrape_images.py — 对缺图商品重抓1688主图(5张)+详情图(≥10张), 原地更新 douyin_product_data.jsonl

用法:
  python fix_scrape_images.py --limit N     # 只处理前N个
  python fix_scrape_images.py --test        # 试跑2个不写盘
进度: image_fix_progress.json (done/failed, 断点续跑)
"""
import asyncio
import json
import os
import random
import re
import sys
import time

import requests
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9223"
DATA = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_product_data.jsonl"
TMP = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/tmp_douyin"
PROGRESS = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/image_fix_progress.json"
OFFER_URL = "https://detail.1688.com/offer/{}.html"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def img_url(uri):
    if not uri:
        return None
    if uri.startswith('http'):
        return uri
    return 'https://cbu01.alicdn.com/' + uri.lstrip('/')


def download(url, path):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(path, 'wb') as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


def load_data():
    data = {}
    order = []
    with open(DATA, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            oid = str(r.get('offerId'))
            if oid in data:
                continue
            data[oid] = r
            order.append(oid)
    return data, order


def save_data(data, order):
    tmp = DATA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for oid in order:
            f.write(json.dumps(data[oid], ensure_ascii=False) + '\n')
    if os.path.exists(DATA):
        os.replace(DATA, DATA + '.bak')
    os.replace(tmp, DATA)


def load_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding='utf-8') as f:
            return json.load(f)
    return {"done": [], "failed": []}


def save_progress(p):
    tmp = PROGRESS + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PROGRESS)


def deficient(rec):
    mains = [p for p in (rec.get('main_imgs') or []) if os.path.exists(p)]
    dets = rec.get('detail_imgs') or []
    return len(mains) < 5 or len(dets) < 10


async def fetch_main_images_from_dom(page):
    """1688 详情页 DOM 抓 cbu 商品主图(非缩略图)"""
    try:
        return await page.evaluate("""() => {
            return [...document.querySelectorAll('img')]
                .map(i => i.src || i.dataset.src || '').filter(Boolean)
                .filter(u => u.includes('cbu01'))
                .filter(u => !/_(sum|search)\\./.test(u) && !u.endsWith('.svg'))
                .filter((u, i, a) => a.indexOf(u) === i);
        }""")
    except Exception:
        return []


async def fetch_desc_images(page, want=20):
    """滚动+展开折叠模块, 收集'商品详情'区描述大图 (凑够 want 张提前停)"""
    try:
        stable, last_h = 0, 0
        for _ in range(60):
            await page.evaluate("window.scrollBy(0, 900)")
            await asyncio.sleep(0.25)
            h = await page.evaluate("() => document.body.scrollHeight")
            if h == last_h:
                stable += 1
                if stable >= 4:
                    break
            else:
                stable, last_h = 0, h
        await page.evaluate("""() => {
            const heads = [...document.querySelectorAll(
                '.od-collapse-module .collapse-header, [class*="collapse"] [class*="header"]')];
            for (const h of heads) {
                try { h.dispatchEvent(new MouseEvent('click', {bubbles: true})); } catch (e) {}
            }
        }""")
        await asyncio.sleep(1.5)
        for _ in range(40):
            await page.evaluate("window.scrollBy(0, 900)")
            await asyncio.sleep(0.22)
            h = await page.evaluate("() => document.body.scrollHeight")
            if h == last_h:
                stable += 1
                if stable >= 4:
                    break
            else:
                stable, last_h = 0, h
        await asyncio.sleep(0.8)
        urls = await page.evaluate("""() => {
            const at = (el) => el.getBoundingClientRect().top + window.scrollY;
            let anchorY = null, endY = null;
            for (const m of document.querySelectorAll('.od-collapse-module, [class*="collapse-module"]')) {
                const head = m.querySelector('[class*="collapse-header"], [class*="header"]');
                const t = head ? (head.textContent || '').trim() : '';
                if (anchorY === null && /商品详情|图文详情|宝贝详情|产品详情/.test(t)) anchorY = at(head);
                if (/同款推荐|热门推荐|相关推荐|看了又看|喜欢/.test(t) && endY === null) endY = at(head);
            }
            const out = [];
            const seen = new Set();
            const keep = (img) => {
                const u = img.src || img.dataset.src || img.getAttribute('data-tfs-src') || '';
                if (!u || !u.includes('cbu01')) return;
                if (/_(sum|search)\\./.test(u) || u.endsWith('.svg')) return;
                if (img.naturalWidth > 0 && img.naturalWidth < 400) return;
                const key = u.split('?')[0];
                if (seen.has(key)) return;
                seen.add(key);
                out.push({u, y: at(img)});
            };
            const seenRoots = new Set();
            const walk = (root) => {
                if (!root || seenRoots.has(root)) return;
                seenRoots.add(root);
                for (const el of root.querySelectorAll('*')) {
                    if (el.tagName === 'IMG') keep(el);
                    if (el.shadowRoot) walk(el.shadowRoot);
                }
            };
            walk(document);
            let res = out;
            if (anchorY !== null) res = res.filter(o => o.y >= anchorY - 60);
            if (endY !== null && endY > (anchorY || 0)) res = res.filter(o => o.y < endY);
            res.sort((a, b) => a.y - b.y);
            return res.map(o => o.u);
        }""")
        return urls[:60]
    except Exception:
        return []


async def is_blocked(page):
    """1688 风控/验证码页检测"""
    try:
        t = await page.evaluate("document.body ? document.body.innerText.slice(0,400) : ''")
        u = page.url
        if 'login' in u or 'punish' in u or '_______tmd_____' in u:
            return True
        for k in ('验证码', '滑块', '访问过于频繁', '亲，您访问的页面不存在', '系统繁忙', '请输入验证码'):
            if k in t:
                return True
        return False
    except Exception:
        return False


async def fix_one(page, rec):
    """重抓一个 offer 的主图+详情图, 返回 (ok, main_n, detail_n)"""
    oid = str(rec['offerId'])
    d = os.path.join(TMP, oid)
    os.makedirs(d, exist_ok=True)
    try:
        await page.goto(OFFER_URL.format(oid), wait_until='domcontentloaded', timeout=45000)
    except Exception as e:
        log(f"  ✗ 页面打开失败: {str(e)[:60]}")
        return False, 0, 0
    await page.wait_for_timeout(5000)
    if await is_blocked(page):
        return 'BLOCKED', 0, 0

    # 主图: DOM 前5 + worklist img_uris 兜底
    main_paths = []
    dom_mains = await fetch_main_images_from_dom(page)
    for j, u in enumerate(dom_mains[:5]):
        uu = img_url(u)
        if not uu:
            continue
        p = os.path.join(d, f'main_{j}.jpg')
        if download(uu, p):
            main_paths.append(p)
        if len(main_paths) >= 5:
            break
    if len(main_paths) < 5:
        for uri in rec.get('img_uris', []):
            u = img_url(uri)
            if not u:
                continue
            p = os.path.join(d, f'main_{len(main_paths)}.jpg')
            if download(u, p):
                main_paths.append(p)
            if len(main_paths) >= 5:
                break

    # 详情图: 描述区全量
    detail_urls = await fetch_desc_images(page)
    detail_paths = []
    for j, u in enumerate(detail_urls[:60]):
        p = os.path.join(d, f'detail_{j}.jpg')
        if download(img_url(u), p):
            detail_paths.append(p)
    if len(detail_paths) < 10:
        # 回退: DOM 大图前若干张
        extra = await fetch_main_images_from_dom(page)
        j = len(detail_paths)
        for u in extra:
            if j >= 12:
                break
            uu = img_url(u)
            if not uu:
                continue
            p = os.path.join(d, f'detail_{j}.jpg')
            if download(uu, p):
                detail_paths.append(p)
                j += 1

    rec['main_imgs'] = main_paths
    rec['detail_imgs'] = detail_paths
    return True, len(main_paths), len(detail_paths)


async def main():
    args = sys.argv[1:]
    test = '--test' in args
    limit = 0
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])
    created_only = '--created-only' in args

    data, order = load_data()
    prog = load_progress()
    done_set = set(prog['done'])
    # 已建商品优先(它们在店里等着补图), 未建的排后(供未来创建用)
    try:
        created = set(json.load(open('/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_create_progress.json'))['created'].keys())
    except Exception:
        created = set()
    todo = []
    for oid in order:
        if oid in done_set:
            continue
        rec = data.get(oid)
        if rec is None:
            continue
        if rec.get('created_checked') and not deficient(rec):
            continue
        if deficient(rec):
            todo.append(oid)
    todo.sort(key=lambda oid: 0 if oid in created else 1)
    if created_only:
        todo = [oid for oid in todo if oid in created]
    log(f"缺图待补: {len(todo)} / 数据 {len(order)} (其中已建商品 {sum(1 for o in todo if o in created)} 个优先)")
    if limit:
        todo = todo[:limit]
    if test:
        todo = todo[:2]
    if not todo:
        log("没有待补商品")
        return

    async with async_playwright() as p:
        b = await p.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await ctx.new_page()
        blocked_run = 0
        ok_n = fail_n = 0
        try:
            for i, oid in enumerate(todo):
                rec = data[oid]
                r = await fix_one(page, rec)
                if r == 'BLOCKED':
                    blocked_run += 1
                    log(f"[{i+1}/{len(todo)}] {oid} ⚠ 1688风控, 连续{blocked_run}次")
                    if blocked_run >= 3:
                        log("  连续3次风控 → 冷却 25 分钟")
                        save_data(data, order)
                        if not test:
                            save_progress(prog)
                        await asyncio.sleep(25 * 60)
                        blocked_run = 0
                    if not test:
                        prog['failed'].append(oid)
                        save_progress(prog)
                    await asyncio.sleep(20)
                    continue
                blocked_run = 0
                ok, mn, dn = r
                if ok and mn >= 5 and dn >= 10:
                    if not test:
                        prog['done'].append(oid)
                        if oid in prog['failed']:
                            prog['failed'].remove(oid)
                    ok_n += 1
                    log(f"[{i+1}/{len(todo)}] {oid} ✓ 主图{mn} 详情{dn}")
                elif ok:
                    if not test:
                        prog['failed'].append(oid)
                    fail_n += 1
                    log(f"[{i+1}/{len(todo)}] {oid} ⚠ 补后仍不足: 主图{mn} 详情{dn}")
                else:
                    if not test:
                        prog['failed'].append(oid)
                    fail_n += 1
                    log(f"[{i+1}/{len(todo)}] {oid} ✗ 失败")
                if not test and (i % 5 == 4):
                    save_data(data, order)
                    save_progress(prog)
                await asyncio.sleep(random.uniform(4, 6))
        finally:
            save_data(data, order)
            save_progress(prog)
            try:
                await page.close()
            except Exception:
                pass
            await b.close()
    log(f"结束: 成功 {ok_n}, 失败/仍不足 {fail_n}")
    if test:
        log("TEST 模式未写盘标记, 数据文件已更新(供检查)")


asyncio.run(main())
