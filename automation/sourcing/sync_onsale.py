#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_onsale.py — 铺货平台「销售中」清单每日扫描 → onsale_snapshot (2026-10-19)

spec: docs/superpowers/specs/2026-10-19-onsale-refactor-design.md §3.1
控制台「商品状态: 销售中」是前端过滤, 行内带 店铺商品状态/货源状态/货源价格/货源库存
(2026-10-19 中午探针实测, /tmp/noon_recon.json)。

用法:
  venv/bin/python sync_onsale.py --dry-run     # 扫描不落库, 打印样本
  venv/bin/python sync_onsale.py --pages 2     # 限页数
  venv/bin/python sync_onsale.py               # 全量 9 页 + 快照 + 对账/超卖告警
"""
import asyncio
import re
import sys
import time

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')

ROW_ITEM_RE = re.compile(r"ID：?(\d{8,})")
ROW_TRIPLE_RE = re.compile(r"(销售中|仓库中|已下架)\s*([\d.]+)元\s*(\d+)")
CHIP_KEYS = ("销售中", "仓库中", "已关联货源", "未关联货源", "关联货源已下架", "价格倒挂")


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def parse_row_text(txt):
    """tr.innerText → dict; 无 item_id 返回 None"""
    m = ROW_ITEM_RE.search(txt or "")
    if not m:
        return None
    row = {"taobao_item_id": int(m.group(1))}
    t = ROW_TRIPLE_RE.search(txt)
    if t:
        row["source_status"], row["source_price"], row["source_stock"] = t.group(1), float(t.group(2)), int(t.group(3))
    else:
        row["source_status"], row["source_price"], row["source_stock"] = "", None, None
    return row


def parse_chip_counts(text):
    """页面文本 → 快捷筛选计数 dict（缺的键为 None）"""
    out = {}
    for key in CHIP_KEYS:
        m = re.search(re.escape(key) + r"[（(]([\d,]+)", text or "")
        out[key] = int(m.group(1).replace(",", "")) if m else None
    return out


def pages_for(total, per_page=100):
    return max(1, -(-total // per_page)) if total else 0


def diff_bindings(today_items, yesterday_items):
    return set(today_items) - set(yesterday_items), set(yesterday_items) - set(today_items)


# ---------- 主扫描流程 ----------

JS_FILTER = """() => {
  const els = [...document.querySelectorAll('span,div,button,a,li')];
  for (const e of els) {
    const t = (e.textContent||'').replace(/\\s+/g,'');
    if ((t === '商品状态:销售中' || t === '销售中') && e.children.length<=2) { e.click(); return t; }
  }
  return null;
}"""

JS_ROWS = """() => {
  const out = [];
  for (const tr of document.querySelectorAll('tr')) {
    const tds = tr.querySelectorAll('td');
    if (tds.length < 5) continue;
    const txt = (tr.innerText||'');
    if (!/ID：?\\d{8,}/.test(txt)) continue;
    out.push(txt.replace(/\\t/g,' ').slice(0, 600));
  }
  return out;
}"""


def upsert_rows(date_str, rows):
    from dbconf import DB_CONFIG
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    sql = ("INSERT INTO onsale_snapshot (snapshot_date, taobao_item_id, source_product_id, "
           "shop_status, source_status, source_price, source_stock, raw) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
           "ON DUPLICATE KEY UPDATE source_product_id=VALUES(source_product_id), shop_status=VALUES(shop_status), "
           "source_status=VALUES(source_status), source_price=VALUES(source_price), source_stock=VALUES(source_stock), raw=VALUES(raw)")
    cur.executemany(sql, [(date_str, r["taobao_item_id"], r.get("source_product_id"), "销售中",
                           r.get("source_status"), r.get("source_price"), r.get("source_stock"),
                           r.get("raw")) for r in rows])
    conn.commit()
    cur.close()
    conn.close()
    return len(rows)


def yesterday_items(date_str):
    from dbconf import DB_CONFIG
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT taobao_item_id FROM onsale_snapshot WHERE snapshot_date = DATE_SUB(%s, INTERVAL 1 DAY)", (date_str,))
    rows = {int(r[0]) for r in cur.fetchall()}
    cur.close()
    conn.close()
    return rows


def write_binding_alerts(new_ids, gone_ids, date_str):
    """按天去重写 sync_alert（与 detect_alerts.detect_source_dead 同一去重口径，先 SELECT 再 INSERT）"""
    from dbconf import DB_CONFIG
    import pymysql
    if not new_ids and not gone_ids:
        return 0
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    n = 0
    for kind, ids, msg in (("新增", new_ids, f"在售清单新增 {len(new_ids)} 个商品"),
                           ("消失", gone_ids, f"在售清单消失 {len(gone_ids)} 个商品（下架/删除，若在售则超卖风险）")):
        if not ids:
            continue
        cur.execute("SELECT COUNT(*) FROM sync_alert WHERE alert_type='onsale_binding_change' AND status=0 "
                    "AND message LIKE %s AND DATE(create_time)=%s", (f"%在售清单{kind}%", date_str))
        if cur.fetchone()[0]:
            continue
        cur.execute("INSERT INTO sync_alert (alert_type, message, status, create_time) VALUES (%s,%s,0,NOW())",
                    ("onsale_binding_change", msg))
        n += 1
    conn.commit()
    cur.close()
    conn.close()
    return n


def write_stock_alerts(rows_map, low_threshold=10):
    """超卖风险/低库存告警（spec §3.6，按天去重）。rows_map: item_id → row"""
    from dbconf import DB_CONFIG
    import pymysql
    oversell = [r for r in rows_map.values()
                if r.get("source_status") == "已下架" or r.get("source_stock") == 0]
    low = [r for r in rows_map.values()
           if r.get("source_stock") is not None and 0 < r["source_stock"] <= low_threshold]
    if not oversell and not low:
        return 0
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    n = 0
    for atype, items, msg in (
            ("oversell_risk", oversell,
             f"超卖风险: {len(oversell)} 个在售商品货源已下架/0库存 (含ID {','.join(str(r['taobao_item_id']) for r in oversell[:5])}...)"),
            ("low_stock", low,
             f"低库存: {len(low)} 个在售商品货源库存≤{low_threshold} (含ID {','.join(str(r['taobao_item_id']) for r in low[:5])}...)")):
        if not items:
            continue
        cur.execute("SELECT COUNT(*) FROM sync_alert WHERE alert_type=%s AND status=0 AND DATE(create_time)=%s",
                    (atype, time.strftime('%Y-%m-%d')))
        if cur.fetchone()[0]:
            continue
        cur.execute("INSERT INTO sync_alert (alert_type, message, status, create_time) VALUES (%s,%s,0,NOW())",
                    (atype, msg))
        n += 1
    conn.commit()
    cur.close()
    conn.close()
    return n


async def scan(args):
    from cdp_utils import connect_cdp
    from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli
    import isv_stock_sync as S  # 复用 goto_page / set_page_size / body_text
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com"], log=log)
    page = None
    rows_map = {}
    try:
        page = await open_page(ctx, quiet=True)
        await minimize_windows_quiet(ctx)
        fr = await get_frame(page)
        if not fr:
            log("!! 没找到 isv-container iframe（登录态掉了？）")
            return 2
        if not await fr.locator(".ant-table-row").first.count():
            await nav_to_guanli(fr)
        clicked = await fr.evaluate(JS_FILTER)
        await asyncio.sleep(4)
        body = await S.body_text(fr)
        chips = parse_chip_counts(body)
        total = chips["销售中"]
        log(f"筛选点击: {clicked}; 快捷筛选: {chips}")
        if not total:
            log("!! 销售中计数为 0（筛选没生效/登录态掉了）")
            return 2
        if not await S.set_page_size(fr):
            await asyncio.sleep(5)
            if not await S.set_page_size(fr):
                return 3
        pages = pages_for(total)
        if args.pages:
            pages = min(pages, args.pages)
        for pg in range(1, pages + 1):
            if pg > 1 and not await S.goto_page(fr, pg):
                log(f"!! 第 {pg} 页跳转失败, 用已得数据继续")
                break
            await asyncio.sleep(2)
            for txt in await fr.evaluate(JS_ROWS):
                r = parse_row_text(txt)
                if r:
                    r["raw"] = txt[:1000]
                    rows_map[r["taobao_item_id"]] = r
            log(f"page {pg}/{pages}: 累计 {len(rows_map)}")
        # source_product_id 反查（taobao_offer_map: taobao_item_id → source_product_id）
        from dbconf import DB_CONFIG
        import pymysql
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        for iid, r in rows_map.items():
            cur.execute("SELECT source_product_id FROM taobao_offer_map WHERE taobao_item_id=%s LIMIT 1", (iid,))
            hit = cur.fetchone()
            r["source_product_id"] = int(hit[0]) if hit and hit[0] is not None else None
        cur.close()
        conn.close()
        if rows_map:
            log(f"样本: {list(rows_map.values())[0]}")
        date_str = time.strftime('%Y-%m-%d')
        if args.dry_run:
            log(f"[dry-run] 共 {len(rows_map)} 行, 未落库")
            return 0
        n = upsert_rows(date_str, list(rows_map.values()))
        log(f"入库 {n} 条")
        old = yesterday_items(date_str)
        new_ids, gone_ids = diff_bindings(set(rows_map), old)
        alerts = write_binding_alerts(new_ids, gone_ids, date_str)
        n_stock = write_stock_alerts(rows_map)
        log(f"对账: 新增 {len(new_ids)} 消失 {len(gone_ids)}, 绑定告警 {alerts}, 超卖/低库存告警 {n_stock}")
        # 进度文件（看板卡片 list_progress 消费）
        import json
        json.dump({"date": date_str, "total": total, "rows": len(rows_map),
                   "oversell": sum(1 for r in rows_map.values() if r.get("source_status") == "已下架" or r.get("source_stock") == 0),
                   "low": sum(1 for r in rows_map.values() if r.get("source_stock") is not None and 0 < r["source_stock"] <= 10),
                   "time": time.strftime('%Y-%m-%d %H:%M')},
                  open('/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/onsale_snapshot_progress.json', 'w'),
                  ensure_ascii=False, indent=1)
        return 0
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass
        # 绝不 b.close()（0 标签病）；守卫 tab 由包装脚本 ensure_chrome 兜底


async def minimize_windows_quiet(ctx):
    try:
        from cdp_utils import minimize_windows
        await minimize_windows(ctx, log=lambda m: None)
    except Exception:
        pass


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pages", type=int, default=0)
    args = ap.parse_args()
    sys.exit(asyncio.run(scan(args)))


if __name__ == "__main__":
    main()
