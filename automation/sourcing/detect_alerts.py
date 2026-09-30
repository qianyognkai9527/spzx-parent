#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""库存同步提醒检测: 对比 source_sku/source_product 当前状态, 写 sync_alert。
纯 Python + MySQL, 无需浏览器。
用法: detect_alerts.py [--type product_down|sku_down|price_change|all]"""
import json
import os
import sys
import time
from datetime import datetime

import pymysql
from shop_ref import shop_id_of_product

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
LAST_PRICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_prices.json")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def has_unread(cur, alert_type, source_product_id=None, source_sku_id=None):
    """是否已存在未读同类提醒(幂等去重)。"""
    sql = "SELECT COUNT(*) FROM sync_alert WHERE alert_type=%s AND status=0"
    args = [alert_type]
    if source_product_id is not None:
        sql += " AND source_product_id=%s"
        args.append(source_product_id)
    if source_sku_id is not None:
        sql += " AND source_sku_id=%s"
        args.append(source_sku_id)
    cur.execute(sql, args)
    return cur.fetchone()[0] > 0


def insert_alert(cur, alert_type, message, source_product_id=None, source_sku_id=None,
                 platform_product_id=None, platform_sku_id=None, old_value=None, new_value=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 货源侧告警没有对应平台商品，shop_id 留空表示归属未知
    shop_id = shop_id_of_product(cur, platform_product_id)
    cur.execute(
        "INSERT INTO sync_alert (alert_type, source_product_id, source_sku_id, platform_product_id, "
        "platform_sku_id, shop_id, old_value, new_value, message, status, create_time) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s)",
        (alert_type, source_product_id, source_sku_id, platform_product_id,
         platform_sku_id, shop_id, old_value, new_value, message, now))


def detect_product_down(conn):
    """货源商品下架: source_product 被删, 或其所有 source_sku status=0。
    通过 product_bind_relation 找平台商品。"""
    cur = conn.cursor()
    # 条件1: source_product is_deleted=1
    cur.execute("SELECT id, source_product_name FROM source_product WHERE is_deleted=1")
    deleted = cur.fetchall()
    # 条件2: 有 SKU 但全部 status=0
    cur.execute(
        "SELECT sp.id, sp.source_product_name FROM source_product sp "
        "WHERE sp.is_deleted=0 "
        "AND EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id AND ss.is_deleted=0) "
        "AND NOT EXISTS (SELECT 1 FROM source_sku ss WHERE ss.source_product_id=sp.id "
        "AND ss.status=1 AND ss.is_deleted=0)")
    all_down = cur.fetchall()
    down_products = list(deleted) + list(all_down)
    created = 0
    for sp_id, sp_name in down_products:
        if has_unread(cur, "product_down", source_product_id=sp_id):
            continue
        # 找关联平台商品
        cur.execute(
            "SELECT product_id FROM product_bind_relation WHERE source_productId=%s AND is_deleted=0",
            (sp_id,))
        rows = cur.fetchall()
        pp_ids = [r[0] for r in rows]
        msg = f"货源商品下架: {sp_name or sp_id}"
        if pp_ids:
            msg += f" -> 平台商品 {','.join(str(x) for x in pp_ids)}"
        pp_id = pp_ids[0] if pp_ids else None
        insert_alert(cur, "product_down", msg, source_product_id=sp_id, platform_product_id=pp_id)
        created += 1
        log(f"  [product_down] sp={sp_id} {sp_name} -> pp={pp_id}")
    conn.commit()
    cur.close()
    return created


def detect_sku_down(conn):
    """货源SKU下架: source_sku.status=0 且有 sku_bind_relation 关联。
    通过 sku_bind_relation 找平台SKU。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT ss.id, ss.source_product_id, ss.sku_key, ss.stock "
        "FROM source_sku ss "
        "WHERE ss.status=0 AND ss.is_deleted=0 "
        "AND EXISTS (SELECT 1 FROM sku_bind_relation sbr WHERE sbr.source_sku_id=ss.id AND sbr.is_deleted=0)")
    down_skus = cur.fetchall()
    created = 0
    for ss_id, sp_id, sku_key, stock in down_skus:
        if has_unread(cur, "sku_down", source_sku_id=ss_id):
            continue
        cur.execute(
            "SELECT sbr.platform_sku_id FROM sku_bind_relation sbr "
            "WHERE sbr.source_sku_id=%s AND sbr.is_deleted=0", (ss_id,))
        rows = cur.fetchall()
        psk_ids = [r[0] for r in rows]
        msg = f"货源SKU下架: {sku_key} (库存{stock})"
        if psk_ids:
            msg += f" -> 平台SKU {','.join(str(x) for x in psk_ids)}"
        psk_id = psk_ids[0] if psk_ids else None
        insert_alert(cur, "sku_down", msg, source_product_id=sp_id, source_sku_id=ss_id,
                     platform_sku_id=psk_id)
        created += 1
        log(f"  [sku_down] sp={sp_id} sku={ss_id} {sku_key} -> psk={psk_ids}")
    conn.commit()
    cur.close()
    return created


def load_last_prices():
    try:
        with open(LAST_PRICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_last_prices(data):
    with open(LAST_PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect_price_change(conn):
    """货源SKU价格变动: 对比 last_prices.json 中上次价格。
    有未读 price_change 提醒时不重复告警, 且不更新基准价(保留旧值以便下次重新检测)。"""
    last_prices = load_last_prices()
    cur = conn.cursor()
    cur.execute(
        "SELECT ss.id, ss.source_product_id, ss.sku_key, ss.price "
        "FROM source_sku ss "
        "WHERE ss.status=1 AND ss.is_deleted=0 "
        "AND EXISTS (SELECT 1 FROM sku_bind_relation sbr WHERE sbr.source_sku_id=ss.id AND sbr.is_deleted=0)")
    skus = cur.fetchall()
    created = 0
    for ss_id, sp_id, sku_key, price in skus:
        price = float(price) if price is not None else 0.0
        old = last_prices.get(str(ss_id))
        if old is None:
            last_prices[str(ss_id)] = price
            continue
        if abs(price - old) < 0.001:
            continue
        # 价格变动
        if has_unread(cur, "price_change", source_sku_id=ss_id):
            # 已有未读提醒, 不重复告警, 不更新基准价(保留 old 以便用户读后重新检测)
            continue
        cur.execute(
            "SELECT sbr.platform_sku_id FROM sku_bind_relation sbr "
            "WHERE sbr.source_sku_id=%s AND sbr.is_deleted=0", (ss_id,))
        rows = cur.fetchall()
        psk_ids = [r[0] for r in rows]
        psk_id = psk_ids[0] if psk_ids else None
        msg = f"货源SKU价格变动: {sku_key} {old:.2f} -> {price:.2f}"
        if psk_ids:
            msg += f" -> 平台SKU {','.join(str(x) for x in psk_ids)}"
        insert_alert(cur, "price_change", msg, source_product_id=sp_id, source_sku_id=ss_id,
                     platform_sku_id=psk_id, old_value=f"{old:.2f}", new_value=f"{price:.2f}")
        last_prices[str(ss_id)] = price
        created += 1
        log(f"  [price_change] sp={sp_id} sku={ss_id} {sku_key} {old:.2f}->{price:.2f} -> psk={psk_ids}")
    conn.commit()
    cur.close()
    save_last_prices(last_prices)
    return created


def main():
    alert_type = "all"
    for i, a in enumerate(sys.argv):
        if a == "--type" and i + 1 < len(sys.argv):
            alert_type = sys.argv[i + 1]
    valid = {"product_down", "sku_down", "price_change", "all"}
    if alert_type not in valid:
        log(f"非法 --type: {alert_type}, 可选 {valid}")
        sys.exit(1)

    log(f"=== 提醒检测 ({alert_type}) 开始 ===")
    conn = get_conn()
    total = 0
    if alert_type in ("product_down", "all"):
        n = detect_product_down(conn)
        log(f"product_down: 新增 {n} 条")
        total += n
    if alert_type in ("sku_down", "all"):
        n = detect_sku_down(conn)
        log(f"sku_down: 新增 {n} 条")
        total += n
    if alert_type in ("price_change", "all"):
        n = detect_price_change(conn)
        log(f"price_change: 新增 {n} 条")
        total += n
    conn.close()
    log(f"=== 完成: 共新增 {total} 条提醒 ===")


if __name__ == "__main__":
    main()
