#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sku_match_report.json -> DB taobao_offer_map（淘宝 item ↔ 1688 offer ↔ source_product）。

只做映射，不碰 source_sku/source_product 数据本身。offer_id -> source_product_id 在
导入时解析 source_product_url 回填（5847 行里 2367 行是 offer 形态 URL），查询侧免拆 URL。
"""
import json
import os
import re
import sys

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbconf import DB_CONFIG  # noqa: E402

OFFER_RE = re.compile(r"detail\.1688\.com/offer/(\d+)\.html")
DEFAULT_REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sku_match_report.json")


def parse_offer_id(url):
    """从 source_product_url 提取 offer id；非 offer 形态/空返回 None。"""
    if not url:
        return None
    m = OFFER_RE.search(url)
    return int(m.group(1)) if m else None


def refresh_table(items, conn=None):
    """全量 UPSERT taobao_offer_map。items 是 report['items'] 列表（item_id/offer_id 字符串）。

    返回 upsert 行数。传入 conn 时不接管连接生命周期（isv_sku_match 尾部复用连接场景不传也行，
    统一让本函数自管，简单可靠）。
    """
    own = conn is None
    if own:
        conn = pymysql.connect(**DB_CONFIG, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, source_product_url FROM source_product "
                "WHERE source_product_url LIKE '%detail.1688.com/offer/%' AND is_deleted = 0")
            sp_by_offer = {}
            for sp_id, url in cur.fetchall():
                oid = parse_offer_id(url)
                if oid is not None:
                    sp_by_offer[oid] = sp_id
            rows = []
            for it in items:
                item_id = str(it.get("item_id") or "").strip()
                offer_id = str(it.get("offer_id") or "").strip()
                if not item_id.isdigit() or not offer_id.isdigit():
                    continue
                rows.append((int(item_id), int(offer_id), sp_by_offer.get(int(offer_id))))
            if not rows:
                return 0
            cur.executemany(
                "INSERT INTO taobao_offer_map (taobao_item_id, offer_id, source_product_id, update_time) "
                "VALUES (%s, %s, %s, NOW()) "
                "ON DUPLICATE KEY UPDATE offer_id = VALUES(offer_id), "
                "source_product_id = VALUES(source_product_id), update_time = NOW()",
                rows)
            return len(rows)
    finally:
        if own:
            conn.close()


def main():
    report = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REPORT
    with open(report, encoding="utf-8") as f:
        items = json.load(f)["items"]
    n = refresh_table(items)
    print(f"taobao_offer_map upsert {n} rows（report: {report}）")


if __name__ == "__main__":
    main()
