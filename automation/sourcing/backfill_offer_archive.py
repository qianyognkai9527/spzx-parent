#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backfill_offer_archive.py — 补映射 + 全量建档（spec 2026-10-18 P1）。

用法:
  $PY backfill_offer_archive.py --remap          # 步骤1: URL正则补映射, 零采集
  $PY backfill_offer_archive.py --dry-run --limit 3
  $PY backfill_offer_archive.py --limit 500      # 步骤2: 建档, todo 按 DB 现算(映射即进度)
  $PY backfill_offer_archive.py --limit 500 --delay 8 --cooldown 1500
守卫(启动前必查): Chrome 9222 在线、归类v2/品牌/规格匹配不在跑。
纪律: 3-10s/个、风控冷却 25min、夜间轮次避开周六凌晨(collect_full 退役前)。
"""
import argparse, asyncio, json, re, sys, time, traceback
from datetime import datetime

import pymysql

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from dbconf import DB_CONFIG
from cdp_utils import connect_cdp, new_page_quiet
from offer_fetch import fetch_offer
from detect_stock_change import process_changes, load_progress, save_progress

OFFER_RE = re.compile(r"offer/(\d+)")
CDP_PORT = 9222
REPORT = '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/backfill_report.json'


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_report():
    try:
        with open(REPORT, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"remapped": 0, "created": 0, "dead": [], "failed": [], "ts": None}


def save_report(rep):
    rep["ts"] = time.strftime("%F %T")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)


def build_product_row(offer_id, offer):
    """source_product INSERT 参数: (name, code, url, source_price, freight_cost, head_img, source_status, data_source, platform_type)"""
    skus = offer.get("skus") or []
    price = min((s["price"] for s in skus if s.get("price")), default=0)
    status = 0 if offer.get("gone") else 1
    title = offer.get("title") or f"1688货源{offer_id}"
    return (title, offer_id, f"https://detail.1688.com/offer/{offer_id}.html",
            price, 8, offer.get("img"), status, 2, 1)


def remap(conn):
    """URL 正则补映射：source_product_url 抽 offer_id 回填 taobao_offer_map.source_product_id。"""
    cur = conn.cursor()
    cur.execute("SELECT id, source_product_url FROM source_product WHERE is_deleted=0 AND source_product_url LIKE '%detail.1688.com/offer/%'")
    offer2pid = {}
    for pid, url in cur.fetchall():
        m = OFFER_RE.search(url or "")
        if m:
            offer2pid[m.group(1)] = pid
    cur.execute("SELECT id, offer_id FROM taobao_offer_map WHERE source_product_id IS NULL")
    todo = [(mid, oid) for mid, oid in cur.fetchall() if str(oid) in offer2pid]
    for mid, oid in todo:
        cur.execute("UPDATE taobao_offer_map SET source_product_id=%s, update_time=NOW() WHERE id=%s",
                    (offer2pid[str(oid)], mid))
    conn.commit()
    cur.close()
    return len(todo)


def todo_offers(conn, limit):
    """仍无档的绑定 offer：映射即进度——建过档的 source_product_id 已非空自然退出 todo。"""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT offer_id FROM taobao_offer_map WHERE source_product_id IS NULL ORDER BY offer_id" +
                (f" LIMIT {int(limit)}" if limit else ""))
    rows = [str(r[0]) for r in cur.fetchall()]
    cur.close()
    return rows


def archive_one(conn, offer_id, offer):
    """建档: 先查同 code 旧档(2026-10-18 审查修复——08-20 老壳 data_source=2 且 URL 为 NULL,
    --remap 按 URL 补不到, 但 code 就是 offer_id)——命中就绑定旧 pid、不 INSERT
    (旧壳 0 SKU, process_changes 插入即补全; gone 则 UPDATE 旧档 source_status=0, 旧壳没 SKU 可清),
    没有才 INSERT 新档。ORDER BY id DESC: 重复档并存时绑最新一份(带 SKU 的新档), 单行场景行为不变。
    绑定分支再查 URL: NULL 或不含本 offer_id 的壳, 回填规范 detail 地址(2026-10-18 planner 补充裁决)——
    否则旧壳永远进不了 detect_stock_change 的 URL 池(全部要求 LIKE '%detail.1688.com/offer/%'), 采完档也不可监控。
    含本 offer_id 判据锚定 /offer/<id>.html: 线上 2370 条 offer URL 全是该形态, 且防 offer/123 被 offer/1234 串号。
    之后照旧: 回填映射 -> 存活时插SKU -> 写detect进度。返回 (pid, is_new)。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()
    cur.execute("SELECT id, source_product_url FROM source_product WHERE source_product_code=%s AND is_deleted=0 ORDER BY id DESC LIMIT 1", (offer_id,))
    hit = cur.fetchone()
    is_new = not hit
    if hit:
        pid, old_url = hit
        if offer.get("gone"):
            cur.execute("UPDATE source_product SET source_status=0 WHERE id=%s", (pid,))
        if not old_url or f"/offer/{offer_id}.html" not in old_url:
            cur.execute("UPDATE source_product SET source_product_url=%s, data_source=2, crawl_time=%s WHERE id=%s",
                        (f"https://detail.1688.com/offer/{offer_id}.html", now, pid))
            log(f"  ↺ offer={offer_id} 壳回填URL sp={pid}")
    else:
        row = build_product_row(offer_id, offer)
        cur.execute("""INSERT INTO source_product
            (source_product_name, source_product_code, source_product_url, source_price, freight_cost,
             head_img_url, source_status, data_source, platform_type, crawl_time, create_time, is_deleted)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)""", row + (now, now))
        pid = cur.lastrowid
    cur.execute("UPDATE taobao_offer_map SET source_product_id=%s, update_time=NOW() WHERE offer_id=%s", (pid, offer_id))
    conn.commit()
    cur.close()
    if not offer.get("gone") and offer.get("skus"):
        process_changes(pid, offer["skus"])       # 复用 detect_stock_change 的 SKU 插入(旧档为空=补全, 新档=全新插入)
    checked = load_progress()
    checked[pid] = now[:10]                        # 建档=今天已刷过, 免得 P2 T1 把 3000 个新档全当"从未刷新"
    save_progress(checked)
    return pid, is_new


async def run_backfill(args):
    conn = pymysql.connect(**DB_CONFIG)
    todo = todo_offers(conn, args.limit)
    log(f"待建档 {len(todo)} 个 offer")
    if args.dry_run:
        for oid in todo[:5]:
            log(f"  DRY 将采集 offer={oid}")
        conn.close(); return 0
    b, ctx = await connect_cdp(CDP_PORT, keep_urls=["taobao.com", "1688.com"], log=log, minimize=True)
    page = await new_page_quiet(ctx)
    rep = load_report()
    done = failed = ok_count = 0
    consec_fail = 0
    try:
        for oid in todo:
            try:
                offer = await asyncio.wait_for(fetch_offer(page, oid, settle=3.0), timeout=25)
                pid, is_new = archive_one(conn, oid, offer)
                rep["created"] += 1
                ok_count += 1
                consec_fail = 0
                if offer.get("gone"):
                    rep["dead"].append(oid)
                    log(f"  ☠ offer={oid} 已失效, {'建档' if is_new else '绑定旧档'} sp={pid} source_status=0")
                elif is_new:
                    log(f"  ✓ offer={oid} 新建档 sp={pid}, {len(offer.get('skus') or [])} SKU")
                else:
                    log(f"  ↺ offer={oid} 已有档 sp={pid}, 绑定不重建, {len(offer.get('skus') or [])} SKU")
            except Exception as e:
                failed += 1
                consec_fail += 1
                rep["failed"].append(oid)
                log(f"  ✗ offer={oid}: {str(e)[:80]}")
                if consec_fail >= 2:
                    log(f"  ⏸ 连续 {consec_fail} 次采集异常, 冷却 {int(args.cooldown)}s 后继续")
                    await asyncio.sleep(args.cooldown)
                    consec_fail = 0
            done += 1
            if done % 20 == 0:
                log(f"进度 {done}/{len(todo)} created={rep['created']} dead={len(rep['dead'])} failed={failed}")
            if done % 50 == 0:
                save_report(rep)
            if ok_count and ok_count % 100 == 0:
                log(f"  ⏸ 成功 {ok_count} 个, 休 60s")
                await asyncio.sleep(60)
            await asyncio.sleep(args.delay)
    finally:
        save_report(rep)
        try: await page.close()
        except Exception: pass
        try: await b.close()
        except Exception: pass
    conn.close()
    log(f"完成: created={rep['created']} dead={len(rep['dead'])} failed={failed}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remap", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--cooldown", type=float, default=1500.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        if args.remap:
            conn = pymysql.connect(**DB_CONFIG)
            n = remap(conn)
            conn.close()
            rep = load_report()
            rep["remapped"] = n
            save_report(rep)
            log(f"补映射回填 {n} 行")
            return
        rc = asyncio.get_event_loop().run_until_complete(run_backfill(args))
    except Exception:
        traceback.print_exc(); rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
