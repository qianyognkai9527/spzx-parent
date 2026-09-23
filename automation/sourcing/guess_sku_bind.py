#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动猜测 SKU 关联: 按归一化名称匹配 source_sku <-> platform_sku, 生成 sku_bind_relation 草稿(status=0)。
归一化: 去空格、全角半角统一、分隔符统一(> / | 统一为空)、大小写统一。
仅处理 product_bind_relation 中已关联的商品对。
用法: guess_sku_bind.py [--test](只处理前10个商品对)"""
import re
import sys
import time
from datetime import datetime

import pymysql

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def normalize(s):
    """归一化 SKU key: 黑色>XXL / 黑色/XXL / 黑色 XXL -> 黑色xxl"""
    if not s:
        return ""
    s = s.replace("&gt;", ">")
    s = re.sub(r"[>/\\|]+", "", s)
    s = re.sub(r"\s+", "", s)
    s = s.lower()
    s = s.replace("色", "").replace("码", "")
    return s


def load_pairs(test):
    """加载已关联的商品对: (platform_product_id, source_product_id)"""
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""SELECT r.product_id, r.source_productId
                   FROM product_bind_relation r
                   WHERE r.is_deleted=0""")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows[:10] if test else rows


def load_skus(product_id, is_source):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    if is_source:
        cur.execute("SELECT id, sku_key FROM source_sku WHERE source_product_id=%s AND is_deleted=0 AND status=1", (product_id,))
    else:
        cur.execute("SELECT id, sku_key FROM platform_sku WHERE platform_product_id=%s AND is_deleted=0", (product_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def insert_bind(platform_sku_id, source_sku_id):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT id FROM sku_bind_relation WHERE platform_sku_id=%s AND source_sku_id=%s AND is_deleted=0",
                (platform_sku_id, source_sku_id))
    if not cur.fetchone():
        cur.execute("INSERT INTO sku_bind_relation (platform_sku_id, source_sku_id, status, match_type, create_time, update_time) "
                    "VALUES (%s,%s,0,'auto',%s,%s)",
                    (platform_sku_id, source_sku_id, now, now))
        conn.commit()
    cur.close()
    conn.close()


def main():
    test = "--test" in sys.argv
    pairs = load_pairs(test)
    log(f"待匹配 {len(pairs)} 个商品对")
    matched = unmatched = 0
    for plat_pid, src_pid in pairs:
        plat_skus = load_skus(plat_pid, False)
        src_skus = load_skus(src_pid, True)
        # 归一化索引: normalized_key -> source_sku_id
        src_index = {}
        for sid, skey in src_skus:
            nk = normalize(skey)
            if nk:
                src_index[nk] = sid
        for pid, pkey in plat_skus:
            nk = normalize(pkey)
            if nk and nk in src_index:
                insert_bind(pid, src_index[nk])
                matched += 1
            else:
                unmatched += 1
    log(f"完成: 匹配 {matched} 个 SKU, 未匹配 {unmatched} 个")


if __name__ == "__main__":
    main()
