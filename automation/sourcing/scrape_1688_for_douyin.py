"""scrape_1688_for_douyin.py — 抓1688详情: 主图/SKU/尺码图, 为抖店新建准备数据"""
import asyncio
import json
import os
import random
import re
import sys
import time
import requests
from cdp_utils import connect_cdp

WORKLIST = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_worklist.jsonl"
OUT = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/douyin_product_data.jsonl"
TMP = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/tmp_douyin"
SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"


def resolve_paths():
    """支持 --worklist / --data 覆盖默认路径(独立批次用不同文件避免互相冲突)"""
    global WORKLIST, OUT, TMP
    args = sys.argv[1:]
    if '--worklist' in args:
        WORKLIST = args[args.index('--worklist') + 1]
    if '--data' in args:
        OUT = args[args.index('--data') + 1]
    os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
    TMP = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/tmp_douyin"


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


def load_done():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        done.add(json.loads(line)['offerId'])
                    except Exception:
                        pass
    return done


def load_worklist():
    out = []
    with open(WORKLIST, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


async def fetch_desc_images(page):
    """滚动+展开折叠模块后, 从'商品详情'collapse 模块内收集描述大图 URL (按页面顺序去重).

    2024+ 版 1688 详情页把描述区放在默认折叠的 od-collapse-module 里, 必须先展开。
    无匹配模块时回退: '商品详情'文字锚点Y以下的大图。工厂展示页等返回 []。
    """
    try:
        stable, last_h = 0, 0
        for _ in range(60):
            await page.evaluate("window.scrollBy(0, 900)")
            await asyncio.sleep(0.3)
            h = await page.evaluate("() => document.body.scrollHeight")
            if h == last_h:
                stable += 1
                if stable >= 5:
                    break
            else:
                stable, last_h = 0, h
        # 展开所有折叠模块 (描述区默认折叠, 不展开则只有占位缩略图)
        await page.evaluate("""() => {
            const heads = [...document.querySelectorAll(
                '.od-collapse-module .collapse-header, [class*="collapse"] [class*="header"]')];
            for (const h of heads) {
                try { h.dispatchEvent(new MouseEvent('click', {bubbles: true})); } catch (e) {}
            }
        }""")
        await asyncio.sleep(2)
        # 展开后新内容挂载, 再滚动加载一轮
        for _ in range(40):
            await page.evaluate("window.scrollBy(0, 900)")
            await asyncio.sleep(0.25)
            h = await page.evaluate("() => document.body.scrollHeight")
            if h == last_h:
                stable += 1
                if stable >= 5:
                    break
            else:
                stable, last_h = 0, h
        await asyncio.sleep(1)
        return await page.evaluate("""() => {
            const at = (el) => el.getBoundingClientRect().top + window.scrollY;
            // 锚点: 商品详情折叠头 Y; 上界: 推荐区头 Y
            let anchorY = null, endY = null;
            for (const m of document.querySelectorAll('.od-collapse-module, [class*="collapse-module"]')) {
                const head = m.querySelector('[class*="collapse-header"], [class*="header"]');
                const t = head ? (head.textContent || '').trim() : '';
                if (anchorY === null && /商品详情|图文详情|宝贝详情|产品详情/.test(t)) anchorY = at(head);
                if (/同款推荐|热门推荐|相关推荐|看了又看|喜欢/.test(t) && endY === null) endY = at(head);
            }
            // 递归遍历主 DOM + 开放 shadowRoot
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
    except Exception:
        return []


async def scrape_one(page, rec):
    """打开详情页, 抓结构化 SKU (queryofferskuselectormodel API) + 主图下载"""
    offer_id = rec['offerId']
    d = os.path.join(TMP, offer_id)
    os.makedirs(d, exist_ok=True)

    # 结构化 SKU
    sku = await fetch_sku(page, offer_id)
    if not sku:
        log(f"  ⚠ {offer_id} 无SKU数据")
        sku = {"colors": [], "sizes": []}

    # 防串号: goto 失败/被劫持时页面还停在上一家, 继续 DOM 抓图会张冠李戴
    if f'/offer/{offer_id}.html' not in (page.url or ''):
        raise RuntimeError(f"页面未在 offer {offer_id} 详情页(当前 {str(page.url)[:60]}), 跳过防串号")
    # 美甲/穿戴甲: 颜色即花色, 以 DOM 的完整颜色列表为准 (API 颜色 prop 常是配件规格名)
    if rec.get('category') == '美甲' or '穿戴甲' in (rec.get('title') or '') or '美甲' in (rec.get('title') or ''):
        dom_sku = await fetch_sku_from_dom(page, offer_id)
        if dom_sku['colors']:
            sku['colors'] = dom_sku['colors']

    # 主图: 从详情页 DOM 抓 cbu 商品主图(非缩略图), 取前5张
    main_paths = []
    dom_mains = await fetch_main_images_from_dom(page)
    for j, u in enumerate(dom_mains[:5]):
        uu = img_url(u)
        if not uu:
            continue
        p = os.path.join(d, f'main_{j}.jpg')
        if await asyncio.to_thread(download, uu, p):
            main_paths.append(p)
        if len(main_paths) >= 5:
            break
    # 若 DOM 主图不足5张, 补 worklist 的 img_uris
    if len(main_paths) < 5:
        for uri in rec.get('img_uris', []):
            u = img_url(uri)
            if not u:
                continue
            p = os.path.join(d, f'main_{len(main_paths)}.jpg')
            if await asyncio.to_thread(download, u, p):
                main_paths.append(p)
            if len(main_paths) >= 5:
                break

    # 详情图: 描述区锚点以下的大图全量抓取 (≥10张; 工厂展示页等无锚点时回退旧逻辑)
    detail_urls = await fetch_desc_images(page)
    detail_paths = []
    if detail_urls:
        for j, u in enumerate(detail_urls[:60]):
            p = os.path.join(d, f'detail_{j}.jpg')
            if await asyncio.to_thread(download, img_url(u), p):
                detail_paths.append(p)
        log(f"  详情图: 源{len(detail_urls)}张 -> 下载{len(detail_paths)}张")
    if len(detail_paths) < 8:
        # 回退: DOM 大图序列前5张 (旧行为)
        detail_paths = []
        dom_imgs = await fetch_main_images_from_dom(page)
        for j, u in enumerate(dom_imgs):
            uu = img_url(u)
            if not uu:
                continue
            p = os.path.join(d, f'detail_{j}.jpg')
            if await asyncio.to_thread(download, uu, p):
                detail_paths.append(p)
            if len(detail_paths) >= 5:
                break

    # 尺码图候选: 详情页 cbu 主图里挑一张 (启发式; 需人工校准)
    size_chart_img = await fetch_size_chart(page)
    if size_chart_img:
        p = os.path.join(d, 'size_chart.jpg')
        if await asyncio.to_thread(download, img_url(size_chart_img), p):
            size_chart_img = p
        else:
            size_chart_img = None

    return {"offerId": offer_id, "title": rec.get('title', ''),
            "source_price": rec.get('source_price'),
            "main_imgs": main_paths,
            "detail_imgs": detail_paths,
            "sku": sku,
            "size_chart_img": size_chart_img,
            "category": rec.get('category', '')}


async def fetch_main_images_from_dom(page):
    """从详情页 DOM 抓 cbu 主图 (非缩略图)"""
    try:
        return await page.evaluate("""() => {
            return [...document.querySelectorAll('img')]
                .map(i => i.src || i.dataset.src || '').filter(Boolean)
                .filter(u => u.includes('cbu01.alicdn.com')
                    && !/_(sum|search)\\./.test(u) && !u.endsWith('.svg'));
        }""")
    except Exception:
        return []


async def fetch_sku(page, offer_id):
    """监听 queryofferskuselectormodel API 返回结构化 SKU"""
    sku = {"colors": [], "sizes": []}
    queue = asyncio.Queue()

    async def on_resp(r):
        try:
            if SKU_API in r.url:
                body = await r.text()
                if 'skuProps' in body:
                    await queue.put(body)
        except Exception:
            pass

    def _dispatch(r):
        asyncio.create_task(on_resp(r))

    page.on('response', _dispatch)
    try:
        try:
            await page.goto(f"https://detail.1688.com/offer/{offer_id}.html",
                            wait_until='domcontentloaded')
        except Exception as e:
            log(f"  goto 异常: {str(e)[:60]}")
            return sku
        await asyncio.sleep(3)

        try:
            body = await asyncio.wait_for(queue.get(), timeout=10)
        except asyncio.TimeoutError:
            # 降级: 从页面文本抓
            return await fetch_sku_from_dom(page, offer_id)

        try:
            data = json.loads(body)
            props = data['data']['skuSelectorBizModel'].get('skuProps', [])
            for pr in props:
                name = pr.get('prop') or ''
                vals = [v.get('name', '') for v in pr.get('value', []) if v.get('name')]
                if '颜色' in name or '色' in name:
                    sku['colors'] = vals[:30]
                elif '尺码' in name or '码' in name:
                    sku['sizes'] = vals[:30]
        except Exception as e:
            log(f"  SKU 解析失败: {str(e)[:60]}")
        # 若 API 没抓到颜色/尺码, 从 DOM 兜底补
        if not sku['colors'] or not sku['sizes']:
            dom_sku = await fetch_sku_from_dom(page, offer_id)
            if not sku['colors'] and dom_sku['colors']:
                sku['colors'] = dom_sku['colors']
            if not sku['sizes'] and dom_sku['sizes']:
                sku['sizes'] = dom_sku['sizes']
        return sku
    finally:
        # 移除监听: 否则每商品挂一个 handler, 长跑后响应事件派生 N 个陈旧 task
        page.remove_listener('response', _dispatch)


async def fetch_sku_from_dom(page, offer_id):
    """降级: 从详情页文本提取尺码/颜色"""
    sku = {"colors": [], "sizes": []}
    try:
        txt = await page.evaluate('() => document.body.innerText')
        m = re.search(r'尺码[：:\s]*([^\n]{2,60})', txt)
        if m:
            sku['sizes'] = [s.strip() for s in re.split(r'[、,，/\s]+', m.group(1)) if s.strip()][:30]
        # 颜色: 匹配 '颜色\tBY1229天姿绝色,BY1309...' 形式 (逗号/顿号分隔)
        mc = re.search(r'颜色[：:\s]*([^\n]{2,200})', txt)
        if mc:
            sku['colors'] = [c.strip() for c in re.split(r'[、,，/\s]+', mc.group(1)) if c.strip()][:30]
    except Exception:
        pass
    return sku


async def fetch_size_chart(page):
    """启发式找尺码图: 详情页 cbu 主图里选一张非商品正面图 (后续人工校准)"""
    try:
        imgs = await page.evaluate("""() => {
            return [...document.querySelectorAll('img')].map(i=>i.src||i.dataset.src||'').filter(Boolean);
        }""")
        mains = [u for u in imgs if 'cbu01.alicdn.com' in u
                 and not any(s in u for s in ('_sum', '_search', '.svg'))]
        if not mains:
            return None
        # 尺码图通常是详情图序列里含参数表的那张; 取序列中部偏后的1张作为候选
        return mains[min(len(mains) // 2, len(mains) - 1)]
    except Exception:
        return None


def load_existing_data():
    out, bad = [], 0
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        bad += 1
    if bad:
        log(f"⚠ {OUT} 有 {bad} 行解析失败被忽略(refill/redetail 重写时这些行会丢失)")
    return out


async def main():
    resolve_paths()
    test = '--test' in sys.argv
    refill = '--refill' in sys.argv
    limit = 0
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    worklist = load_worklist()
    if refill:
        # 重抓: 只处理现有数据里颜色缺失的行, 重写整个 jsonl
        existing = load_existing_data()
        bad_ids = {r['offerId'] for r in existing if not r['sku']['colors']}
        todo = [r for r in worklist if r['offerId'] in bad_ids]
        if test:
            todo = todo[:1]
        elif limit:
            todo = todo[:limit]
        log(f"[refill] 数据 {len(existing)}, 待补颜色 {len(bad_ids)}, 本次 {len(todo)}")
        if not todo:
            log("无待补商品")
            return
        good = [r for r in existing if r['offerId'] not in bad_ids]

        b, ctx = await connect_cdp(9223, keep_urls=["fanqienovel.com", "fxg.jinritemai.com"], log=log)
        page = await ctx.new_page()
        fixed = []
        try:
            for i, rec in enumerate(todo):
                log(f"[{i+1}/{len(todo)}] refill {rec['offerId']}")
                try:
                    data = await scrape_one(page, rec)
                except Exception as e:
                    log(f"  ✗ 异常: {str(e)[:80]}")
                    continue
                fixed.append(data)
                log(f"  颜色{len(data['sku']['colors'])}, 尺码{data['sku']['sizes'][:6]}")
                await asyncio.sleep(random.uniform(3, 5))
            all_rows = good + fixed
            tmp_out = OUT + '.tmp'
            with open(tmp_out, 'w', encoding='utf-8') as f:
                for r in all_rows:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            os.replace(tmp_out, OUT)
            log(f"[refill] 完成: 修复 {len(fixed)} 条, 共 {len(all_rows)} 条 -> {OUT}")
        finally:
            try:
                await page.close()
            except Exception:
                pass
            try:
                await b.close()
            except Exception:
                pass
        return

    redetail = '--redetail' in sys.argv
    if redetail:
        # 重采描述图: 对现有数据里 detail_imgs < 8 张的行, 轻量重开详情页抓描述区
        existing = load_existing_data()
        todo = [r for r in existing if len(r.get('detail_imgs') or []) < 8]
        if test:
            todo = todo[:1]
        elif limit:
            todo = todo[:limit]
        lack = len(todo)
        log(f"[redetail] 数据 {len(existing)}, 描述图不足 {lack} 条, 本次 {len(todo)}")
        if not todo:
            log("无待重采商品")
            return

        b, ctx = await connect_cdp(9223, keep_urls=["fanqienovel.com", "fxg.jinritemai.com"], log=log)
        page = await ctx.new_page()
        ok_cnt = 0
        try:
            for i, rec in enumerate(todo):
                offer_id = rec['offerId']
                log(f"[{i+1}/{len(todo)}] redetail {offer_id} (原{len(rec.get('detail_imgs') or [])}张)")
                urls = []
                for attempt in (0, 1):
                    try:
                        await page.goto(f"https://detail.1688.com/offer/{offer_id}.html",
                                        wait_until='domcontentloaded', timeout=45000)
                        await asyncio.sleep(3)
                        urls = await fetch_desc_images(page)
                    except Exception as e:
                        log(f"  goto/抓取异常: {str(e)[:60]}")
                        urls = []
                    if urls:
                        break
                    if attempt == 0:
                        log("  ⚠ 无描述图(疑似限流), 冷却600s后重试")
                        await asyncio.sleep(600)
                if not urls:
                    log(f"  ✗ 仍无描述图, 保留原{len(rec.get('detail_imgs') or [])}张")
                    continue
                d = os.path.join(TMP, offer_id)
                os.makedirs(d, exist_ok=True)
                paths = []
                for j, u in enumerate(urls[:60]):
                    p = os.path.join(d, f'detail_{j}.jpg')
                    if os.path.exists(p) and os.path.getsize(p) > 1000:
                        paths.append(p)
                        continue
                    if await asyncio.to_thread(download, img_url(u), p):
                        paths.append(p)
                rec['detail_imgs'] = paths
                ok_cnt += 1
                log(f"  ✓ 源{len(urls)}张 -> 下载{len(paths)}张")
                # 每条原子重写 (断点安全)
                tmp_out = OUT + '.tmp'
                with open(tmp_out, 'w', encoding='utf-8') as f:
                    for r in existing:
                        f.write(json.dumps(r, ensure_ascii=False) + '\n')
                os.replace(tmp_out, OUT)
                await asyncio.sleep(random.uniform(3, 5))
        finally:
            log(f"[redetail] 完成: 成功 {ok_cnt}/{len(todo)} -> {OUT}")
            try:
                await page.close()
            except Exception:
                pass
            await b.close()
        return

    done = load_done()
    todo = [r for r in worklist if r['offerId'] not in done]
    if test:
        todo = todo[:1]
    elif limit:
        todo = todo[:limit]
    log(f"工作清单 {len(worklist)}, 已抓 {len(done)}, 本次 {len(todo)}")

    b, ctx = await connect_cdp(9223, keep_urls=["fanqienovel.com", "fxg.jinritemai.com"], log=log)
    page = await ctx.new_page()
    try:
        for i, rec in enumerate(todo):
            log(f"[{i+1}/{len(todo)}] {rec['offerId']}")
            try:
                data = await scrape_one(page, rec)
            except Exception as e:
                log(f"  ✗ 异常: {str(e)[:80]}")
                continue
            with open(OUT, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
            log(f"  主图{len(data['main_imgs'])}张, 颜色{len(data['sku']['colors'])}, 尺码{data['sku']['sizes'][:8]}, 尺码图{'有' if data['size_chart_img'] else '无'}")
            await asyncio.sleep(random.uniform(3, 5))
        log(f"完成: 新增 {len(todo)} 条 -> {OUT}")
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
