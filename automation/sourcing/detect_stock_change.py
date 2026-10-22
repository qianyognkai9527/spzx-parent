#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量变化检测: 采集 1688 SKU -> 与上次 source_sku 对比 -> 有变化的写 inventory_change_log -> 更新 stock。
用法: detect_stock_change.py [--limit N] [--test]"""
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime

import pymysql
from playwright.async_api import async_playwright

from dbconf import DB_CONFIG
from offer_fetch import fetch_offer
from cdp_utils import new_page_quiet
CDP = "http://127.0.0.1:9222"
SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"
PROGRESS_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/detect_stock_pool_progress.json"
FETCH_TIMEOUT = 25  # 单个商品抓取超时(秒)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


POOL_SQL = {
    # 优质池: 优质货品(A/B) OR 优质供应商(A/B)旗下货品
    "ab": (
        "SELECT id, source_product_url FROM source_product sp "
        "WHERE sp.is_deleted=0 AND sp.source_product_url LIKE '%detail.1688.com/offer/%' "
        "AND (sp.quality_grade IN ('A','B') OR EXISTS ("
        "  SELECT 1 FROM source_factory f WHERE f.id=sp.source_factory_id "
        "  AND f.is_deleted=0 AND f.quality_grade IN ('A','B')))"
    ),
    "all": "SELECT id, source_product_url FROM source_product WHERE is_deleted=0 AND source_product_url LIKE '%detail.1688.com/offer/%'",
    # 优质池 ∪ 绑定池。实测两者交集为 0（并集 851 = 315 + 536），所以这个池子不是"略大一点"，
    # 而是把断货告警唯一可能有数据的那 536 个货源纳进来。配合 --max-per-run 限制单轮请求数。
    "both": (
        "SELECT DISTINCT id, source_product_url FROM ("
        "  SELECT sp.id, sp.source_product_url FROM source_product sp "
        "  WHERE sp.is_deleted=0 AND sp.source_product_url LIKE '%detail.1688.com/offer/%' "
        "  AND (sp.quality_grade IN ('A','B') OR EXISTS ("
        "    SELECT 1 FROM source_factory f WHERE f.id=sp.source_factory_id "
        "    AND f.is_deleted=0 AND f.quality_grade IN ('A','B')))"
        "  UNION "
        "  SELECT sp2.id, sp2.source_product_url FROM source_product sp2 "
        "  JOIN product_bind_relation br ON br.source_productId = sp2.id AND br.is_deleted = 0 "
        "  JOIN platform_product p ON p.id = br.product_id "
        "  WHERE sp2.is_deleted=0 AND sp2.source_product_url LIKE '%detail.1688.com/offer/%'"
        ") t"
    ),
    # 绑定池: 被平台商品绑定的货源 —— 断货告警真正需要的是这一批。
    # 但**不是默认值**：实测 3529 个被绑定货源与优质池(A/B,315 个)交集为 0，
    # 把它们全量纳入意味着 05:00 的无人值守任务从 0 个变成 3529 个 1688 请求，
    # 那是账号级风控暴露（跨 Chrome 实例也会互触），开闸时机必须由人决定。
    "binding": (
        "SELECT DISTINCT sp.id, sp.source_product_url FROM source_product sp "
        "JOIN product_bind_relation br ON br.source_productId = sp.id AND br.is_deleted = 0 "
        "JOIN platform_product p ON p.id = br.product_id "
        "WHERE sp.is_deleted=0 AND sp.source_product_url LIKE '%detail.1688.com/offer/%'"
    ),
}

# 分级刷新宇宙：铺货绑定的货源（淘宝映射 ∪ 平台商品绑定），不带绑定的纯选品候选不进日常刷新
TIERED_SQL = (
    "SELECT DISTINCT sp.id, sp.source_product_url FROM source_product sp "
    "WHERE sp.is_deleted=0 AND sp.source_product_url LIKE '%detail.1688.com/offer/%' "
    "AND ( EXISTS (SELECT 1 FROM taobao_offer_map tm WHERE tm.source_product_id = sp.id) "
    "   OR EXISTS (SELECT 1 FROM product_bind_relation br WHERE br.source_productId = sp.id AND br.is_deleted = 0))"
)
MIN_STOCK_SQL = (
    "SELECT source_product_id, MIN(stock) FROM source_sku "
    "WHERE is_deleted=0 AND status=1 AND stock IS NOT NULL GROUP BY source_product_id"
)


def load_products(limit, test, pool="ab"):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    sql = POOL_SQL.get(pool) or POOL_SQL["ab"]
    if test:
        sql += " LIMIT 3"
    elif limit:
        sql += f" LIMIT {int(limit)}"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    out = []
    for pid, url in rows:
        m = re.search(r"offer/(\d+)", url or "")
        if m:
            out.append((pid, m.group(1)))
    return out


def get_old_skus(product_id):
    """返回 {sku_key: (id, stock)} 上次快照"""
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, sku_key, stock FROM source_sku WHERE source_product_id=%s AND is_deleted=0 AND status=1", (product_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {k: (sid, st) for sid, k, st in rows}


async def fetch_source_skus(page, offer_id):
    captured = {}

    async def on_resp(r):
        if SKU_API in r.url:
            try:
                captured["body"] = await r.text()
            except Exception:
                pass

    page.on("response", lambda r: asyncio.create_task(on_resp(r)))
    await page.goto(f"https://detail.1688.com/offer/{offer_id}.html", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    if "body" not in captured:
        return []
    try:
        data = json.loads(captured["body"])
        m = data.get("data", {}).get("skuSelectorBizModel", {})
        info = m.get("skuInfoMap", {})
    except Exception:
        return []
    out = []
    for key, sv in info.items():
        if not isinstance(sv, dict):
            continue
        out.append({
            "sku_key": key.replace("&gt;", ">"),
            "sku_id": str(sv.get("skuId", "")),
            "stock": int(sv.get("canBookCount", 0)),
            "price": float(sv.get("price", 0)),
            "spec_id": str(sv.get("specId", "")),
        })
    return out


def process_changes(product_id, new_skus):
    """对比新旧, 写流水, 更新 source_sku。返回 (changed, total)"""
    old = get_old_skus(product_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    changed = 0
    for s in new_skus:
        old_data = old.get(s["sku_key"])
        if old_data:
            old_id, old_stock = old_data
            if old_stock != s["stock"]:
                change = s["stock"] - old_stock
                # 写流水
                cur.execute("INSERT INTO inventory_change_log (source_sku_id, source_product_id, old_stock, new_stock, change_amount, change_type, sync_time, create_time) "
                            "VALUES (%s,%s,%s,%s,%s,'auto',%s,%s)",
                            (old_id, product_id, old_stock, s["stock"], change, now, now))
                # 更新 stock
                cur.execute("UPDATE source_sku SET stock=%s, price=%s, update_time=%s WHERE id=%s",
                            (s["stock"], s["price"], now, old_id))
                changed += 1
        else:
            # 新 SKU, 插入
            cur.execute("INSERT INTO source_sku (source_product_id, sku_key, sku_id, spec_id, stock, price, status, create_time, update_time) "
                        "VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s)",
                        (product_id, s["sku_key"], s["sku_id"], s["spec_id"], s["stock"], s["price"], now, now))
            changed += 1
    conn.commit()
    cur.close()
    conn.close()
    return changed, len(new_skus)


def load_progress():
    """{source_product_id: 上次检测日(ISO)}。

    旧格式是 `{"done":[id,...]}` —— 那是个**永久名单**：处理过一次就再也不回头看。
    于是"库存变化检测"只在首轮有效，之后每天扫 0 个还报 success，实测停摆到 08-13
    都没人发现（台账压根不报行数）。读到旧格式一律视为"很久以前查过"，本轮全部重查。
    """
    try:
        import os
        if os.path.exists(PROGRESS_FILE):
            raw = json.load(open(PROGRESS_FILE))
            checked = raw.get("checked") or {}
            return {int(k): v for k, v in checked.items()}
    except Exception:
        pass
    return {}


def save_progress(checked):
    """原子写：先 .tmp 再 replace，避免 cron 被 kill 时留下半个 JSON 把进度全冲掉。"""
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"checked": {str(k): v for k, v in checked.items()}}, f)
    os.replace(tmp, PROGRESS_FILE)


def due_by_staleness(checked, stale_days, today=None):
    """返回该重查的货源 id 集合：从未查过、记录日期读不出、或超过 stale_days 的。

    纯函数，便于单测。日期解析失败一律当"该重查"处理 —— 宁可多查一次，
    也不要因为一条脏记录让某个货源永久不再被检测（那正是这次的故障形态）。
    """
    today = today or datetime.now().date()
    out = set()
    for pid, stamp in checked.items():
        try:
            last = datetime.strptime(str(stamp)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            out.add(pid)
            continue
        if (today - last).days >= int(stale_days):
            out.add(pid)
    return out


def select_tiered(universe, checked, min_stocks, dead_ids, day_of_year, t1_threshold=100, monday=False):
    """返回 (t1, t2, t3)。T1=低库存/从未刷新/无SKU 每日刷；T2=其余按 (pid+doy)%7 每周一天；
    T3=失效周检(仅周一)。纯函数，日期无关可测。"""
    t1, t2, t3 = [], [], []
    for pid, _oid in universe:
        pid = int(pid)
        if pid in dead_ids:
            if monday:
                t3.append(pid)
            continue
        ms = min_stocks.get(pid)
        if (ms is not None and ms < t1_threshold) or ms is None or pid not in checked:
            t1.append(pid)
            continue
        if (pid + int(day_of_year)) % 7 == 0:
            t2.append(pid)
    return t1, t2, t3


def mark_source_status(product_id, status):
    """tiered 路径的货源生死落库：1=正常(仅 NULL/0 时升级，不覆盖人工标记)
    0=失效(gone；本轮不动 SKU 由调用方保证)。"""
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    if status == 1:
        cur.execute("UPDATE source_product SET source_status=1 WHERE id=%s AND (source_status IS NULL OR source_status=0)", (product_id,))
    else:
        cur.execute("UPDATE source_product SET source_status=0 WHERE id=%s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()


def ensure_guard_tab():
    """浏览器至少留1个标签, 防 0 target 导致下次 connect 报 Browser context management not supported"""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:9222/json/new?https://www.taobao.com", method='PUT')
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass


async def main():
    test = "--test" in sys.argv
    pool = "ab"
    stale_days = 14
    limit = None
    tiered = "--tiered" in sys.argv
    # tiered 分级刷新的默认节奏与 --pool 系不同：量大（宇宙是全部绑定货源）、
    # 请求更密一档也安全（每日只刷 T1 小头 + T2 七分之一轮转）
    max_per_run = 600 if tiered else 60
    delay = 5.0 if tiered else 10.0
    t1_threshold = 100
    stop_hour = 0
    for i, a in enumerate(sys.argv):
        if a == "--pool":
            pool = "ab"
        elif a == "--pool-binding":
            pool = "binding"
        elif a == "--pool-both":
            pool = "both"
        elif a == "--full":
            pool = "all"
        elif a == "--stale-days" and i + 1 < len(sys.argv):
            stale_days = max(1, int(sys.argv[i + 1]))
        elif a == "--max-per-run" and i + 1 < len(sys.argv):
            max_per_run = max(1, int(sys.argv[i + 1]))
        elif a == "--delay" and i + 1 < len(sys.argv):
            delay = max(2.0, float(sys.argv[i + 1]))
        elif a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        elif a == "--t1-threshold" and i + 1 < len(sys.argv):
            t1_threshold = max(1, int(sys.argv[i + 1]))
        elif a == "--stop-hour" and i + 1 < len(sys.argv):
            stop_hour = max(0, int(sys.argv[i + 1]))
    tier_counts = None
    if tiered:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(TIERED_SQL)
        universe = []
        for p, u in cur.fetchall():
            m = re.search(r"offer/(\d+)", u or "")
            if m:
                universe.append((int(p), m.group(1)))
        cur.execute(MIN_STOCK_SQL)
        min_stocks = {int(r[0]): int(r[1]) for r in cur.fetchall()}
        cur.execute("SELECT id FROM source_product WHERE is_deleted=0 AND source_status=0")
        dead_ids = {int(r[0]) for r in cur.fetchall()}
        cur.close()
        conn.close()
        checked = load_progress()
        monday = datetime.now().weekday() == 0
        t1, t2, t3 = select_tiered(universe, checked, min_stocks, dead_ids,
                                   datetime.now().timetuple().tm_yday,
                                   t1_threshold=t1_threshold, monday=monday)
        oid_of = dict(universe)
        selected = t1 + t2 + t3
        pre = len(selected)
        if test:
            selected = selected[:3]           # --test 只试 3 个（与旧路径 load_products 的 LIMIT 3 同义）
        elif limit:
            selected = selected[:int(limit)]
        else:
            selected = selected[:max_per_run]
        deferred = max(0, pre - len(selected))
        todo = [(pid, oid_of[pid]) for pid in selected]
        products = universe
        tier_counts = (len(t1), len(t2), len(t3))
        pool = "tiered"
        log(f"tiered: T1={len(t1)} T2={len(t2)} T3={len(t3)} 本轮={len(todo)}"
            f"（t1_threshold={t1_threshold}, 死链复查{'含' if monday else '不含(非周一)'}, "
            f"受单轮上限 {max_per_run} 顺延 {deferred} 个）")
    else:
        products = load_products(limit, test, pool)
        checked = load_progress()
        # 只重查"到期"的：stale_days 天内查过的跳过。旧格式(永久 done 名单)一律视为到期
        due = due_by_staleness(checked, stale_days)
        todo = [(pid, oid) for pid, oid in products if pid in due or pid not in checked]
        # 单轮上限：1688 是账号级风控、跨 Chrome 实例也会互触，而兄弟脚本 collect_1688_full
        # 用的是 15~25 秒间隔 + 1200 秒冷却。这里靠"量少 + 间隔大"把 851 个池子摊到多天，
        # 而不是像以前那样一轮扫完 —— 宁可库存数据晚几天新鲜，也不拿账号去换。
        deferred = max(0, len(todo) - max_per_run)
        if not test and not limit:
            todo = todo[:max_per_run]
        log(f"池={pool} 候选 {len(products)} 个，本轮重查 {len(todo)} 个"
            f"（{stale_days} 天内查过的跳过 {len(products) - len(todo) - deferred} 个，"
            f"受单轮上限 {max_per_run} 顺延 {deferred} 个）")
    async with async_playwright() as pw:
        b = await pw.chromium.connect_over_cdp(CDP)
        ctx = b.contexts[0]
        page = await new_page_quiet(ctx)
        total_changed = 0
        processed = 0
        sku_counts_file = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/sku_counts.json"
        try:
            sku_counts = json.load(open(sku_counts_file)) if os.path.exists(sku_counts_file) else {}
        except Exception:
            sku_counts = {}
        today = datetime.now().strftime("%Y-%m-%d")
        for pid, offer_id in todo:
            # 硬停钟：到点后不再开新页（把 9222 让给 05:30 ISV 同步），只对 tiered 生效
            if tiered and stop_hour and int(time.strftime('%H')) >= stop_hour and not test:
                log("硬停钟触发, 提前收工")
                break
            try:
                if tiered:
                    res = await asyncio.wait_for(fetch_offer(page, offer_id), timeout=FETCH_TIMEOUT)
                    if res.get("gone"):
                        # 已失效：标 source_status=0，本轮不动 SKU；周一 T3 复查，复活则标回 1
                        mark_source_status(pid, 0)
                        skus = None
                        log(f"  ✗ product={pid} offer={offer_id} 已失效(下架/不存在), source_status=0")
                    else:
                        skus = res.get("skus") or []
                        if skus:
                            mark_source_status(pid, 1)
                else:
                    skus = await asyncio.wait_for(fetch_source_skus(page, offer_id), timeout=FETCH_TIMEOUT)
                if skus is not None:
                    changed, total = process_changes(pid, skus)
                    total_changed += changed
                    if skus:
                        sku_counts[offer_id] = {"count": len(skus), "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
                    if changed:
                        log(f"  product={pid} offer={offer_id} -> {changed}/{total} SKU 有变化")
            except asyncio.TimeoutError:
                log(f"  ✗ product={pid} 抓取超时({FETCH_TIMEOUT}s), 跳过")
            except Exception as e:
                log(f"  ✗ product={pid} 异常: {str(e)[:80]}")
            # 抓失败也记日期：否则一个永久报错的货源会每天被重查、把整轮时间吃光。
            # 报错本身已经逐条打出来了，不会因为记了日期就看不见。
            checked[pid] = today
            save_progress(checked)
            processed += 1
            if len(checked) % 20 == 0:
                json.dump(sku_counts, open(sku_counts_file, "w"), ensure_ascii=False)
            await asyncio.sleep(delay)
        json.dump(sku_counts, open(sku_counts_file, "w"), ensure_ascii=False)
        ensure_guard_tab()
        await page.close()
    # 机器可解析的一行，供 inventory_cron.sh 写台账：扫了 0 个也要能被发现
    tier_part = f" tier=t1:{tier_counts[0]},t2:{tier_counts[1]},t3:{tier_counts[2]}" if tier_counts else ""
    print(f"SUMMARY pool={pool} candidates={len(products)} checked={processed} "
          f"changed={total_changed} deferred={deferred}{tier_part}")
    log(f"完成: 检测 {processed} 个货源, {total_changed} 个 SKU 有变化, 已写流水")


if __name__ == "__main__":
    asyncio.run(main())
