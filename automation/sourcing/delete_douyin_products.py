#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""delete_douyin_products.py — 删除抖店指定商品(情趣内衣类目33个 + nomatch已建5个)
机制: 页面内 fetch 抓全量商品列表 → 精确 product_id / 唯一全标题匹配 → batchDelete → 复核。
删除进抖店回收站, 可恢复(restore_recycle.py)。
用法: python delete_douyin_products.py [--dry-run] [--test]
"""
import asyncio
import json
import os
import sys
import time

from cdp_utils import connect_cdp

CDP_PORT = 9223
BASE = os.path.dirname(os.path.abspath(__file__))
TARGETS = os.path.join(BASE, "douyin_delete_targets.json")
PROGRESS = os.path.join(BASE, "douyin_delete_progress.json")
LIST_URL = "https://fxg.jinritemai.com/ffa/g/list"
API_BASE = "/product/tproduct/list?page={page}&pageSize=100&draft_status=0&comment_percent=&group_id=&sku_type=&tab=all&business_type=4&is_online=1&not_for_sale_search_type=1&from_mng=1&check_status=3&status=0&order_field=offline_time&sort=desc&appid=1"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def grab_all_products(page):
    all_items = []
    page_idx = 0
    while True:
        url = API_BASE.format(page=page_idx)
        try:
            res = await page.evaluate("""async (u) => {
                const r = await fetch(u, {credentials:'include'});
                return await r.json();
            }""", url)
            data = res.get('data', [])
            if not isinstance(data, list) or len(data) == 0:
                break
            for it in data:
                pid = str(it.get('product_id', ''))
                name = it.get('name', '')
                if pid:
                    all_items.append({'product_id': pid, 'name': name})
            total = int(res.get('total', 0) or 0)
            if page_idx == 0:
                log(f"店铺商品总数: {total}")
            if len(all_items) >= total or len(data) < 100:
                break
        except Exception as e:
            log(f"  页{page_idx} 异常: {str(e)[:50]}")
            break
        page_idx += 1
        await asyncio.sleep(0.5)
    log(f"抓到 {len(all_items)} 个商品")
    return all_items


async def batch_delete(page, product_ids):
    deleted = 0
    for i in range(0, len(product_ids), 50):
        batch = product_ids[i:i + 50]
        ok = False
        for ep in ("/product/tproduct/batchDelete", "/product/tproduct/batchDeleteDraft"):
            try:
                res = await page.evaluate("""async (arg) => {
                    const r = await fetch(arg.ep, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        credentials: 'include',
                        body: JSON.stringify({product_ids: arg.ids})
                    });
                    return await r.json();
                }""", {"ep": ep, "ids": batch})
                code = res.get('code', -1)
                if code == 0:
                    deleted += len(batch)
                    log(f"  批次{i//50+1}: {ep.rsplit('/',1)[-1]} 删除{len(batch)}个成功")
                    ok = True
                    break
                log(f"  批次{i//50+1}: {ep.rsplit('/',1)[-1]} code={code} msg={str(res.get('msg',''))[:60]}")
            except Exception as e:
                log(f"  批次{i//50+1}: {ep} 异常 {str(e)[:70]}")
        if not ok:
            log(f"  批次{i//50+1}: 全部端点失败, 本批保留")
        await asyncio.sleep(1)
    return deleted


async def main():
    dry_run = '--dry-run' in sys.argv
    test = '--test' in sys.argv
    tg = json.load(open(TARGETS))
    by_pid = {str(k): str(v) for k, v in tg.get("by_pid", {}).items()}          # offer->pid (catblocked)
    by_title = {str(k): str(v) for k, v in tg.get("by_title", {}).items()}      # offer->title (nomatch saved)
    target_pids = set(by_pid.values())
    log(f"目标: 精确pid {len(target_pids)} 个 + 标题匹配 {len(by_title)} 个")

    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["fanqienovel.com", "fxg.jinritemai.com"], log=log)
    page = None
    for p in ctx.pages:
        if 'fxg.jinritemai.com' in p.url:
            page = p
            break
    if not page:
        page = await ctx.new_page()
    await page.goto(LIST_URL, wait_until='domcontentloaded', timeout=40000)
    await asyncio.sleep(5)

    items = await grab_all_products(page)
    name2pid = {}
    for it in items:
        name2pid.setdefault(it['name'], []).append(it['product_id'])

    del_pids, matched_titles = [], []
    for it in items:
        if it['product_id'] in target_pids:
            del_pids.append(it['product_id'])
    for offer, title in by_title.items():
        hits = name2pid.get(title, [])
        if len(hits) == 1:
            del_pids.append(hits[0])
            matched_titles.append((offer, title[:30], hits[0]))
        elif len(hits) > 1:
            log(f"⚠ 标题多匹配跳过(需人工): {title[:30]} -> {hits}")
    del_pids = list(dict.fromkeys(del_pids))
    log(f"精确pid命中 {len(target_pids & {i['product_id'] for i in items})} | 标题唯一命中 {len(matched_titles)} | 共待删 {len(del_pids)}")
    for o, t, p in matched_titles:
        log(f"  标题匹配: {o} -> {p} ({t})")

    not_found = target_pids - {i['product_id'] for i in items}
    if not_found:
        log(f"⚠ 列表中未找到 {len(not_found)} 个pid(可能已删/不在该视图): {list(not_found)[:5]}")

    if dry_run:
        log("dry-run: 不执行删除")
        await b.close()
        return
    if test:
        del_pids = del_pids[:1]
        log(f"test: 只删第一个 {del_pids}")

    if not del_pids:
        log("无可删项")
        await b.close()
        return
    deleted = await batch_delete(page, del_pids)

    # 复核
    await asyncio.sleep(3)
    items2 = await grab_all_products(page)
    pids2 = {i['product_id'] for i in items2}
    gone = [p for p in del_pids if p not in pids2]
    log(f"复核: 目标 {len(del_pids)} | API成功 {deleted} | 列表已消失 {len(gone)}")

    json.dump({"deleted": del_pids, "gone_verified": gone,
               "not_found_in_list": sorted(not_found),
               "time": time.strftime("%Y-%m-%d %H:%M:%S")},
              open(PROGRESS, "w"), ensure_ascii=False, indent=1)
    await b.close()


if __name__ == '__main__':
    asyncio.run(main())
