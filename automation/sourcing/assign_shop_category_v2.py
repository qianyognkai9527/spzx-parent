#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并版归类 v2 (9222): 店铺中分类 + SKU调价 + 尺码缺口记录, 撞风控 exit 42 降级跑货源销量计算

在 assign_shop_category.py (v1) 基础上增加:
  1. SKU调价: 新价 = (货源价+130) + (旧SKU价-最低旧价)/r, r=最低旧价/货源价(实测历史倍率, 无货源价则3.9)
     - 旧价来源=编辑页 SKU 现价(平台真值); 货源价=platform_product→product_bind_relation→source_product.source_price
     - 一口价同步=新最低价; 成功后 UPDATE platform_product.pricing
  2. 尺码缺口: 被禁用/无价格的 SKU 行(如未启用的 XL/XXL)记录到 sizegap, 待货源 SKU 数据齐全后再做启用同步
  3. 风控: process_one 返回 risk → 保存进度 → exit(42), 由 run_cat_v2.sh 接力跑 detect_stock_change.py --pool

用法: python assign_shop_category_v2.py [--test|--limit N|--start N|--retry-failed|--ids id1,id2,...]
进度: shop_cat_v2_progress.json (done/failed/skipped/noprice/sizegap)
"""
import asyncio
import json
import os
import random
import re
import sys
import time
import traceback

import pymysql

from cdp_utils import connect_cdp
from assign_shop_category import (
    log, load_plan,
    handle_recommend_dialog, wait_edit_ready, scroll_edit_page,
    check_listing_mode, ensure_extract_way, set_shop_category,
    click_submit, cleanup_leaked_tabs,
)

CDP_PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
PLAN_FILE = os.path.join(BASE, "shop_cat_plan.json")
PROGRESS_FILE = os.path.join(BASE, "shop_cat_v2_progress.json")
EDIT_URL = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true"
DB_CONFIG = {"host": "localhost", "port": 3306, "user": "root",
             "password": "root123456", "database": "db_spzx", "charset": "utf8mb4"}
PRICE_ADD = 130          # 新价 = 货源价 + 130
DEFAULT_RATIO = 3.9      # 无货源价时按历史均值反推
PRICE_MIN, PRICE_MAX = 60, 500   # 合理区间告警线(不拦截只告警)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            d = json.load(open(PROGRESS_FILE, encoding='utf-8'))
            d.setdefault("noprice", [])
            d.setdefault("sizegap", {})
            return d
        except Exception:
            pass
    return {"done": [], "failed": {}, "skipped": [], "noprice": [], "sizegap": {}}


def save_progress(prog):
    # v1 的 save_progress 写 v1 进度文件, 这里必须自己实现(锁+磁盘合并, 含 v2 新增键)
    lock_fd = open(PROGRESS_FILE + '.lock', 'w')
    try:
        import fcntl
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        disk = load_progress()
        merged = {
            "done": sorted(set(disk['done']) | set(prog['done'])),
            "skipped": sorted(set(disk['skipped']) | set(prog['skipped'])),
            "noprice": sorted(set(disk.get('noprice', [])) | set(prog.get('noprice', []))),
            "failed": {**disk.get('failed', {}), **prog.get('failed', {})},
            "sizegap": {**disk.get('sizegap', {}), **prog.get('sizegap', {})},
        }
        tmp = PROGRESS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=1)
        os.replace(tmp, PROGRESS_FILE)
    finally:
        import fcntl
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def ensure_guard_tab():
    """确保浏览器至少有 1 个标签(0 target 会让下一次 connect_over_cdp 报
    Browser context management is not supported). 用 /json/new 补开守卫 tab."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:9222/json/new?https://www.taobao.com", method='PUT')
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception:
        return False


def load_price_anchor():
    """itemId -> source_price (product_bind_relation 绑定的货源价)"""
    plan = load_plan()
    codes = [str(r['itemId']) for r in plan]
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    anchor = {}
    step = 500
    for i in range(0, len(codes), step):
        chunk = codes[i:i + step]
        ph = ",".join(["%s"] * len(chunk))
        cur.execute(
            f"""SELECT pp.code, sp.source_price FROM platform_product pp
            JOIN product_bind_relation pbr ON pbr.product_id=pp.id AND pbr.is_deleted=0
            JOIN source_product sp ON sp.id=pbr.source_productId
            WHERE pp.code IN ({ph})""", chunk)
        for code, price in cur.fetchall():
            try:
                if price and float(price) > 0:
                    anchor[str(code)] = float(price)
            except Exception:
                pass
    cur.close()
    conn.close()
    return anchor


def update_db_pricing(item_id, new_min):
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("UPDATE platform_product SET pricing=%s WHERE code=%s AND platform_type=1",
                    (round(new_min, 2), str(item_id)))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        log(f"  · DB pricing 更新失败: {str(e)[:60]}")
        return False


async def read_sku_prices(page):
    """读 SKU 区: 价格输入平铺列表 + 无价格(禁用/未启用)行规格.
    返回 (prices, disabled_rows): prices=[{idx, v}], disabled_rows=[{spec, size, disabled}]"""
    info = await page.evaluate("""() => {
        const w = document.getElementById('sell-field-sku');
        if (!w) return {found:false};
        const res = {found:true, prices:[], rows:[]};
        [...w.querySelectorAll('span.fusion-input input, span.next-input input')].forEach((i, idx) => {
            const v = (i.value||'').trim();
            if (v && v.includes('.') && !isNaN(parseFloat(v))) res.prices.push({idx, v: parseFloat(v)});
        });
        const trs = w.querySelectorAll('tr');
        for (const tr of trs) {
            const t = (tr.innerText||'').replace(/\\s+/g,' ').trim();
            if (!t || t.length < 3) continue;
            const hasPrice = [...tr.querySelectorAll('input')].some(i => {
                const v=(i.value||'').trim(); return v && v.includes('.') && !isNaN(parseFloat(v));
            });
            if (!hasPrice) {
                const m = t.match(/[XSsMmLl]{1,4}|均码|\\d{2,3}(?:-\\d{2,3})?/g);
                res.rows.push({spec: t.slice(0,60), size: m ? m.join('/') : '', disabled: /重新启用/.test(t)});
            }
        }
        return res;
    }""")
    if not info.get('found'):
        return [], []
    return info.get('prices', []), info.get('rows', [])


async def update_prices(page, item_id, source_price):
    """改一口价+SKU价. 返回 (ok, msg, new_min, disabled_specs)"""
    # 一口价旧值
    price_loc = page.locator('#sell-field-price input')
    old_base = None
    if await price_loc.count() > 0:
        try:
            raw = await price_loc.first.input_value()
            old_base = float(raw) if raw else None
        except Exception:
            pass
    # SKU 现价: 一次 evaluate 拿全部 (read_sku_prices 的 idx 与 sku_inputs.nth(i) 同源同序,
    # 免逐 input input_value() 的几十次 CDP 往返)
    sku_inputs = page.locator('#sell-field-sku span.fusion-input input, #sell-field-sku span.next-input input')
    init_prices, init_disabled = await read_sku_prices(page)
    old_prices = [(p['idx'], p['v']) for p in init_prices if p['v'] > 0]
    if not old_prices and not old_base:
        return False, '无可识别价格(SKU与一口价均空)', None, []
    # 定价参数
    old_min = min([p for _, p in old_prices], default=None)
    if old_base is not None:
        old_min = old_base if old_min is None else min(old_min, old_base)
    # 幂等: 已是新价(≈货源价+130) → 跳过调价, 防止重跑时倍率失真
    if source_price and old_min and abs(old_min - (source_price + PRICE_ADD)) <= 3:
        return True, f'已是新价({old_min:.2f}≈{source_price}+130), 跳过调价', None, init_disabled
    if source_price and old_min:
        ratio = max(1.5, min(8.0, old_min / source_price))
    else:
        ratio = DEFAULT_RATIO
    if source_price:
        new_min = source_price + PRICE_ADD
    elif old_min:
        new_min = round(old_min / DEFAULT_RATIO + PRICE_ADD, 2)
    else:
        return False, '无货源价且无旧价, 无法定价', None, []
    if not (PRICE_MIN <= new_min <= PRICE_MAX):
        log(f"  ⚠ 新最低价 {new_min} 超出合理区间(锚={source_price}, 旧min={old_min})")
    # 填一口价
    if await price_loc.count() > 0:
        try:
            await price_loc.first.scroll_into_view_if_needed(timeout=4000)
            await price_loc.first.click(timeout=4000)
            await price_loc.first.fill(f"{new_min:.2f}", timeout=4000)
            await page.keyboard.press('Tab')
        except Exception as e:
            return False, f'一口价填写失败: {str(e)[:50]}', None, []
    # 填 SKU 价 (保差价: 差价按历史倍率还原成货源差价再加锚)
    changed = 0
    for i, old_p in old_prices:
        new_p = round(new_min + (old_p - old_min) / ratio, 2)
        if abs(new_p - old_p) < 0.01:
            continue
        try:
            inp = sku_inputs.nth(i)
            await inp.scroll_into_view_if_needed(timeout=4000)
            await inp.click(timeout=4000)
            await inp.fill(f"{new_p:.2f}", timeout=4000)
            await page.keyboard.press('Tab')
            changed += 1
        except Exception:
            continue
    # 尺码缺口(禁用/未启用行, read_sku_prices 只回无价格行)
    _, disabled = await read_sku_prices(page)
    return True, f'一口价{old_base}->{new_min:.2f}, SKU改价{changed}个(倍率{ratio:.2f})', new_min, disabled


async def verify_by_reload(ctx, item_id, category):
    """提交超时未确认 → 重开编辑页复核: 类目已设置=实际已提交成功(假失败转成功).
    返回 (ok, msg)"""
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), timeout=60000, wait_until='domcontentloaded')
        if not await wait_edit_ready(page, timeout=45):
            return False, '复核: 编辑页加载失败'
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        sel = await page.evaluate("""() => {
            const tags = document.querySelectorAll('#sell-field-shopcat .next-tag');
            return Array.from(tags).map(t=>t.textContent.trim());
        }""")
        if category in sel:
            return True, f'复核确认已提交(类目={category})'
        return False, f'复核: 类目未生效, 当前={sel}'
    except Exception as e:
        return False, '复核异常: ' + str(e)[:50]
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


async def remove_videos(page):
    """删除商品视频区的已上传视频 (淘宝要求 9:16 竖版, 铺货带入的 1:1/16:9 横版会拦提交).
    交互: hover 视频项弹出菜单 → 点「删除」(无确认弹窗).
    返回 (ok, removed)"""
    removed = 0
    for _ in range(6):
        cnt = await page.evaluate("""() => {
            const v = document.querySelector('.sell-component-simply-videos .material-video-item .sell-component-single-video:not(.emptyVideo)');
            return v ? 1 : 0;
        }""")
        if not cnt:
            return True, removed
        try:
            item = page.locator('.sell-component-simply-videos .material-video-item').first
            await item.hover(timeout=5000)
            await page.wait_for_timeout(600)
            delbtn = page.locator('.next-menu-item-text', has_text='删除').last
            await delbtn.click(timeout=4000)
            await page.wait_for_timeout(800)
            removed += 1
        except Exception as e:
            return False, removed
    return True, removed


PRICE_CATS = ("家居服/睡衣", "美甲")   # 用户指令: 调价(货源价+130)只限这两类, 其他类目不动价格
LISTING_OK_STATES = ('放入仓库', '立刻上架')   # 仓库商品维持待上架; 在售商品维持出售中(用户指令 2026-09-24)


async def process_one(ctx, rec, source_price):
    """处理单个商品: 归类+调价. 返回 (status, msg, extra) status: ok/fail/risk"""
    item_id = rec['itemId']
    category = rec['category']
    page = None
    try:
        page = await ctx.new_page()
        await page.goto(EDIT_URL.format(id=item_id), timeout=60000, wait_until='domcontentloaded')
        title = await wait_edit_ready(page)
        if not title:
            return 'fail', '页面加载超时(表单未水合)', None
        rh, rmsg = await handle_recommend_dialog(page)
        if rh:
            log(f"  · {rmsg}")
        await scroll_edit_page(page)
        await asyncio.sleep(1)
        rh2, rmsg2 = await handle_recommend_dialog(page)
        if rh2:
            log(f"  · {rmsg2}")
        lm = await check_listing_mode(page)
        if not lm.get('ok'):
            return 'fail', f'上架状态读取失败: {lm.get("txt")}', None
        if not any(s in lm.get('txt', '') for s in LISTING_OK_STATES):
            return 'fail', f'上架状态异常: {lm.get("txt")}', None
        await ensure_extract_way(page)
        # 调价(仅 家居服/睡衣+美甲; 其他类目不动价格, 失败不阻塞归类)
        if category in PRICE_CATS:
            pok, pmsg, new_min, disabled = await update_prices(page, item_id, source_price)
        else:
            pok, pmsg, new_min, disabled = True, f'非目标类目({category}), 跳过调价', None, []
        if pok:
            log(f"  · {pmsg}")
            if disabled:
                log(f"  · 尺码缺口 {len(disabled)} 行: {[d['size'] for d in disabled][:6]}")
        else:
            log(f"  · 调价跳过: {pmsg}")
        cok, cmsg = await set_shop_category(page, category)
        if not cok:
            return 'fail', f'类目设置失败: {cmsg}', None
        rh3, rmsg3 = await handle_recommend_dialog(page)
        if rh3:
            log(f"  · {rmsg3}")
        # 删除横版视频(1:1/16:9 会拦提交, 淘宝要求 9:16), 用户指令 2026-09-13: 删视频再提交
        vok, vremoved = await remove_videos(page)
        if vremoved:
            log(f"  · 已删除横版视频 {vremoved} 个")
        elif not vok:
            log(f"  · 视频删除失败, 继续尝试提交")
        sok, smsg, risk = await click_submit(page)
        if risk:
            return 'risk', smsg, None
        if not sok and '超时未确认' in smsg:
            # 假失败高发: 重开编辑页实证复核
            vok, vmsg = await verify_by_reload(ctx, item_id, category)
            if vok:
                extra = None  # 价格是否生效未知, 不回填 DB pricing
                return 'ok', f'{category} | {vmsg}', extra
            return 'fail', f'提交失败({vmsg})', None
        if not sok:
            return 'fail', f'提交失败: {smsg}', None
        extra = {'new_min': new_min} if pok and new_min else None
        return 'ok', f'{category} | {smsg}', extra
    except Exception as e:
        estr = str(e)
        if 'Execution context was destroyed' in estr or 'Navigation' in estr:
            # 提交成功跳转瞬间 evaluate 被打断 → 复核实证
            try:
                if page is not None and 'success.htm' in page.url:
                    return 'ok', f'{category} | 提交成功(跳转导航确认)', None
            except Exception:
                pass
            vok, vmsg = await verify_by_reload(ctx, item_id, category)
            if vok:
                return 'ok', f'{category} | {vmsg}', None
            return 'fail', f'提交时页面跳转, 复核未通过({vmsg})', None
        if 'closed' in estr or 'crash' in estr.lower() or 'Target' in estr:
            return 'risk', '页面已失效: ' + estr[:60], None
        return 'fail', estr[:80], None
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass


def build_todo(plan, prog, retry_failed=False, start=0, limit=0, test=False, ids=None):
    """过滤 done/skipped/failed(可选重试) 后按 出售中->仓库->gone/failed 排序; limit/test 在排序后切片"""
    done = set(prog['done'])
    skipped = set(prog['skipped'])
    failed_ids = set(prog['failed'].keys())
    todo = [r for r in plan[start:] if str(r['itemId']) not in done and str(r['itemId']) not in skipped
            and (retry_failed or str(r['itemId']) not in failed_ids)]
    if ids:   # 定向选取(过滤之后, 保持排序); done/skipped 仍剔除, 定向重跑已 done 的会被跳过
        want = set(ids)
        todo = [r for r in todo if str(r['itemId']) in want]

    def sort_key(r):
        iid = str(r['itemId'])
        if iid in failed_ids:
            return 3
        pool = r.get('pool', 'warehouse')
        return 0 if pool == 'onsale' else (1 if pool == 'warehouse' else 2)

    todo.sort(key=sort_key)
    if test:
        todo = todo[:1]
    elif limit:
        todo = todo[:limit]
    return todo


async def main():
    test = '--test' in sys.argv
    limit = 0
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    start = 0
    if '--start' in sys.argv:
        start = int(sys.argv[sys.argv.index('--start') + 1])
    retry_failed = '--retry-failed' in sys.argv
    ids = None
    if '--ids' in sys.argv:
        ids = sys.argv[sys.argv.index('--ids') + 1].split(',')

    plan = load_plan()
    prog = load_progress()
    todo = build_todo(plan, prog, retry_failed=retry_failed, start=start, limit=limit, test=test, ids=ids)
    my_ids = {str(r['itemId']) for r in todo}
    done = set(prog['done'])
    skipped = set(prog['skipped'])
    failed_ids = set(prog['failed'].keys())
    log(f"计划 {len(plan)} 个, v2已完成 {len(done)}, 跳过 {len(skipped)}, 失败 {len(failed_ids)}, 本次处理 {len(todo)}")

    anchor = load_price_anchor()
    log(f"货源价锚点覆盖 {len(anchor)}/{len(plan)} 个商品")

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["myseller.taobao.com", "item.upload.taobao.com"], log=log)
    ensure_guard_tab()  # 防运行中最后一个标签被关导致 0 target

    ok_c = fail_c = risk_c = 0
    for i, rec in enumerate(todo):
        item_id = str(rec['itemId'])
        category = rec['category']
        src_price = anchor.get(item_id)
        t0 = time.time()
        log(f"[{i+1}/{len(todo)}] {item_id} -> {category} (货源价={src_price}) ...")
        status = 'fail'
        msg = ''
        extra = None
        try:
            status, msg, extra = await asyncio.wait_for(process_one(ctx, rec, src_price), timeout=240)
        except asyncio.TimeoutError:
            status, msg = 'fail', '处理超时240s(可能已提交, 待重试)'
            # 复核自身也可能挂死(evaluate 无超时), 须再兜底, 否则 240s 兜底形同虚设
            try:
                vok, vmsg = await asyncio.wait_for(
                    verify_by_reload(ctx, rec['itemId'], rec['category']), timeout=150)
            except asyncio.TimeoutError:
                vok, vmsg = False, '复核超时150s'
            if vok:
                status, msg = 'ok', f"{rec['category']} | {vmsg}"
        except Exception as e:
            status, msg = 'fail', str(e)[:80]
        if status == 'ok':
            ok_c += 1
            prog['done'].append(item_id)
            prog['failed'].pop(item_id, None)
            if extra and extra.get('new_min'):
                update_db_pricing(item_id, extra['new_min'])
            log(f"  ✓ {msg} ({round(time.time()-t0)}s)")
        elif status == 'risk':
            risk_c += 1
            log(f"  ⚠ 风控: {msg}")
        else:
            fail_c += 1
            prog['failed'][item_id] = {'category': category, 'error': msg}
            log(f"  ✗ {msg}")
        save_progress(prog)
        await cleanup_leaked_tabs(ctx, my_ids)
        if status == 'risk':
            log("  风控触发, 保存进度并降级退出(exit 42 → 货源销量计算)")
            ensure_guard_tab()
            await b.close()
            sys.exit(42)
        await asyncio.sleep(random.uniform(3, 5))
        if (i + 1) % 30 == 0:
            rest = random.uniform(25, 35)
            log(f"  已处理 {i+1}, 休息 {int(rest)}s 防风控...")
            await asyncio.sleep(rest)
        if test:
            break

    log(f"完成: 本次成功={ok_c} 失败={fail_c} 风控={risk_c}, 累计 v2done={len(prog['done'])}")
    ensure_guard_tab()
    await b.close()


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
