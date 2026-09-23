#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抖音抖店库存同步: 对已确认(sku_bind_relation.status=1)的抖音商品,
读 1688 货源 SKU 库存, 经抖店"编辑库存"抽屉回写到平台 SKU。

前置: 9223 Chrome 已打开抖店库存管理页
  (https://fxg.jinritemai.com/ffa/g/stock-manage/list)

流程:
1. 查 DB: 已确认的 sku_bind_relation(status=1), 按 platform_product 分组
   --include-drafts 可纳入 status=0 草稿(用于演示/测试)
2. 逐个商品: 搜索定位 -> 开"编辑库存"抽屉 -> 按 SKU ID 匹配货源库存
   -> 填"改后库存" -> 保存(dry-run 则只读不写)
3. 汇总

用法:
  sync_douyin_stock.py                          # 同步所有已确认关联
  sync_douyin_stock.py --test                   # 前 3 个商品
  sync_douyin_stock.py --product-id 93          # 指定 platform_product.id
  sync_douyin_stock.py --dry-run                # 只读, 不写入抖店
  sync_douyin_stock.py --test --dry-run --include-drafts   # 演示流程(用草稿)
"""
import asyncio
import sys
import time

import pymysql
from playwright.async_api import async_playwright

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
CDP = "http://127.0.0.1:9223"
STOCK_URL = "https://fxg.jinritemai.com/ffa/g/stock-manage/list"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_sync_targets(include_drafts, product_id, limit, test):
    """加载待同步商品(按 platform_product 分组)。
    返回 [{pp_id, title, code, items:[{plat_sku_sid(抖店SKU ID), plat_stock, src_stock, status}]}]"""
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    statuses = "1,0" if include_drafts else "1"
    sql = f"""
        SELECT br.status, br.id AS bind_id,
               ps.sku_id AS plat_sku_sid, ps.sku_key AS plat_sku_key, ps.stock AS plat_stock,
               ss.stock AS src_stock, ss.sku_key AS src_sku_key,
               pp.id AS pp_id, pp.title, pp.code
        FROM sku_bind_relation br
        JOIN platform_sku ps ON br.platform_sku_id = ps.id
        JOIN source_sku ss ON br.source_sku_id = ss.id
        JOIN platform_product pp ON ps.platform_product_id = pp.id
        WHERE br.is_deleted = 0 AND ps.platform_type = 2
          AND ps.is_deleted = 0 AND ss.is_deleted = 0
          AND br.status IN ({statuses})
    """
    params = []
    if product_id:
        sql += " AND pp.id = %s"
        params.append(product_id)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    groups = {}
    order = []
    for r in rows:
        pid = r["pp_id"]
        if pid not in groups:
            groups[pid] = {"pp_id": pid, "title": r["title"], "code": r["code"], "items": []}
            order.append(pid)
        groups[pid]["items"].append({
            "plat_sku_sid": r["plat_sku_sid"],   # 抽屉里 "SKU ID" 的匹配键
            "plat_stock": r["plat_stock"],
            "src_stock": r["src_stock"],
            "status": r["status"],
        })
    out = [groups[pid] for pid in order]
    if test:
        out = out[:3]
    elif limit:
        out = out[:limit]
    return out


async def close_drawer(page):
    close = page.locator('.auxo-drawer-close').first
    if await close.count() > 0:
        try:
            await close.click(timeout=3000)
            await page.wait_for_timeout(1200)
        except Exception:
            pass


async def locate_and_open_drawer(page, code):
    """搜索商品(按抖店商品ID code)并在列表中点"编辑库存"开抽屉。返回是否成功。"""
    # 1) 尝试用筛选区搜索框按 code 搜索
    searched = await page.evaluate("""(code) => {
        const inputs = [...document.querySelectorAll('input')].filter(i => {
            const d = i.closest('[class*="drawer"], [class*="Drawer"]');
            return !d && i.offsetParent !== null;
        });
        let target = inputs.find(i => /商品|ID|名称|标题/.test(i.placeholder || ''));
        if (!target && inputs.length) target = inputs[0];
        if (!target) return false;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(target, code);
        target.dispatchEvent(new Event('input', { bubbles: true }));
        const btns = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
        const q = btns.find(b => /查询|搜索|确定/.test(b.textContent.trim()));
        if (q) { q.click(); return true; }
        return false;
    }""", code)
    if searched:
        await page.wait_for_timeout(3000)

    # 2) 在主表格(排除 drawer 内)定位商品行, 点"编辑库存"
    clicked = await page.evaluate("""(pid) => {
        const tables = Array.from(document.querySelectorAll('table'))
            .filter(t => !t.closest('[class*="drawer"]') && !t.closest('[class*="Drawer"]'));
        for (const t of tables) {
            for (const tr of t.querySelectorAll('tr')) {
                const text = tr.innerText || '';
                if (text.includes('商品ID：' + pid) || text.includes('商品ID:' + pid)) {
                    const btn = Array.from(tr.querySelectorAll('button'))
                        .find(b => b.textContent.includes('编辑库存'));
                    if (btn) { btn.click(); return true; }
                }
            }
        }
        return false;
    }""", code)
    if not clicked:
        return False
    await page.wait_for_timeout(3000)
    # 3) 校验抽屉里的商品ID 匹配
    drawer_pid = await page.evaluate("""() => {
        const d = document.querySelector('.auxo-drawer-content');
        if (!d) return null;
        const m = d.innerText.match(/商品ID[：:]\\s*(\\d+)/);
        return m ? m[1] : null;
    }""")
    if drawer_pid and drawer_pid != str(code):
        log(f"    抽屉商品ID不匹配: 期望 {code} 实际 {drawer_pid}")
        await close_drawer(page)
        return False
    return True


async def read_drawer_skus(page):
    """读抽屉里所有 SKU 行: [{sku_id, current_stock}]"""
    return await page.evaluate("""() => {
        const d = document.querySelector('.auxo-drawer-content');
        if (!d) return [];
        const out = [];
        for (const tr of d.querySelectorAll('tr')) {
            const tds = tr.querySelectorAll('td');
            if (tds.length < 2) continue;
            const cell0 = (tds[0].innerText || '').trim();
            const m = cell0.match(/SKU ID[：:]\\s*(\\d+)/);
            if (!m) continue;
            const stockText = (tds[1].innerText || '').trim();
            const stock = parseInt(stockText) || 0;
            out.push({ sku_id: m[1], current_stock: stock });
        }
        return out;
    }""")


async def fill_drawer_stocks(page, target_map):
    """填"改后库存"输入框。target_map: {抖店SKU_ID(str): 新库存(int)}。返回填入数。"""
    return await page.evaluate("""(targets) => {
        const d = document.querySelector('.auxo-drawer-content');
        if (!d) return 0;
        let filled = 0;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        for (const tr of d.querySelectorAll('tr')) {
            const tds = tr.querySelectorAll('td');
            if (tds.length < 2) continue;
            const cell0 = (tds[0].innerText || '').trim();
            const m = cell0.match(/SKU ID[：:]\\s*(\\d+)/);
            if (!m) continue;
            const skuId = m[1];
            if (!(skuId in targets)) continue;
            const inputs = tr.querySelectorAll('input');
            let inp = null;
            for (const i of inputs) {
                const t = (i.type || 'text').toLowerCase();
                if (['checkbox', 'radio', 'hidden', 'button', 'submit', 'image'].includes(t)) continue;
                inp = i; break;
            }
            if (!inp && inputs.length) inp = inputs[inputs.length - 1];
            if (!inp) continue;
            setter.call(inp, String(targets[skuId]));
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            inp.dispatchEvent(new Event('change', { bubbles: true }));
            filled++;
        }
        return filled;
    }""", target_map)


async def click_save(page):
    return await page.evaluate("""() => {
        const root = document.querySelector('.auxo-drawer-footer') || document.querySelector('.auxo-drawer-content');
        if (!root) return false;
        const btns = [...root.querySelectorAll('button')];
        const save = btns.find(b => (b.textContent.includes('保存') || b.textContent.includes('确认')) && !b.disabled);
        if (save) { save.click(); return true; }
        return false;
    }""")


async def main():
    test = "--test" in sys.argv
    dry_run = "--dry-run" in sys.argv
    include_drafts = "--include-drafts" in sys.argv
    product_id = None
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--product-id" and i + 1 < len(sys.argv):
            product_id = int(sys.argv[i + 1])
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    targets = load_sync_targets(include_drafts, product_id, limit, test)
    if not targets:
        log("无符合条件的 sku_bind_relation (status=1 已确认)。")
        log("提示: 加 --include-drafts 可纳入 status=0 草稿用于演示/测试。")
        return

    tag = (" [dry-run 只读]" if dry_run else "") + (" [含草稿]" if include_drafts else "")
    log(f"待同步 {len(targets)} 个抖音商品{tag}")
    for t in targets:
        log(f"  - pp={t['pp_id']} code={t['code']} '{t['title'][:24]}...' ({len(t['items'])} SKU)")

    async with async_playwright() as pw:
        b = await pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        stock_pages = [p for p in ctx.pages if "stock-manage" in p.url]
        if stock_pages:
            page = stock_pages[0]
            log(f"复用库存管理页: {page.url[:60]}")
        else:
            page = await ctx.new_page()
            await page.goto(STOCK_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
        await close_drawer(page)

        done = ok = skipped = 0
        for t in targets:
            done += 1
            pp_id = t["pp_id"]
            code = t["code"]
            title = t["title"]
            log(f"\n[{done}/{len(targets)}] pp={pp_id} code={code} '{title[:24]}...'")
            target_map = {str(it["plat_sku_sid"]): it["src_stock"] for it in t["items"]}
            try:
                opened = await locate_and_open_drawer(page, code)
                if not opened:
                    log(f"    ✗ 未找到商品(搜索/定位失败), 跳过")
                    skipped += 1
                    continue
                drawer_skus = await read_drawer_skus(page)
                log(f"    抽屉 {len(drawer_skus)} SKU, 关联目标 {len(target_map)} SKU")
                matched = 0
                for ds in drawer_skus:
                    sid = ds["sku_id"]
                    if sid in target_map:
                        new_stock = target_map[sid]
                        if ds["current_stock"] != new_stock:
                            log(f"      SKU {sid}: {ds['current_stock']} -> {new_stock}")
                        else:
                            log(f"      SKU {sid}: 已是 {new_stock} (无需改)")
                        matched += 1
                    else:
                        log(f"      SKU {sid}: 无关联货源(跳过)")
                if matched == 0:
                    log(f"    ⚠️ 抽屉无匹配 SKU, 跳过")
                    await close_drawer(page)
                    skipped += 1
                    continue
                if dry_run:
                    log(f"    [dry-run] 不写入, 关闭抽屉")
                    await close_drawer(page)
                    ok += 1
                else:
                    filled = await fill_drawer_stocks(page, target_map)
                    log(f"    填入 {filled} 个 SKU 库存")
                    saved = await click_save(page)
                    if saved:
                        await page.wait_for_timeout(2000)
                        log(f"    ✓ 已保存")
                        ok += 1
                    else:
                        log(f"    ⚠️ 未找到保存按钮")
                    await close_drawer(page)
            except Exception as e:
                log(f"    ✗ 异常: {str(e)[:100]}")
                await close_drawer(page)
            await asyncio.sleep(2)

        log(f"\n完成: 共 {done} 个商品, 成功 {ok}, 跳过 {skipped}"
            + (" [dry-run]" if dry_run else ""))
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
