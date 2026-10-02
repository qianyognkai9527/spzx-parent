#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_promo_columns.py — 核对采集器列清单与两张事实表的真实列是否一致.

来历: 2026-10-02 宝贝粒度第一次真跑就炸在 `Unknown column 'cpm'`，接着又缺
      order_direct / shop_collect —— 采集器的列清单是 Python 侧手写的，
      表结构改了这边不会编译报错，只有跑到那一行才发现。这个脚本把它变成一条命令的静态检查。

跑法: automation/venv/bin/python check_promo_columns.py     # 退出码非 0 = 有不一致
"""
import os
import sys

import pymysql

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cron_batch import DB_CONFIG  # noqa: E402  复用同一份连接配置，不再新增一处硬编码凭据
from collect_alimama_promo import DAILY_COLS, ITEM_COLS  # noqa: E402

TABLES = {"promo_cost_daily": DAILY_COLS, "promo_cost_item_daily": ITEM_COLS}
IGNORE = {"id", "create_time", "update_time"}


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    bad = 0
    for table, cols in TABLES.items():
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=DATABASE() AND table_name=%s", (table,))
        have = {r[0] for r in cur.fetchall()}
        missing = [c for c in cols if c not in have]
        extra = sorted(have - set(cols) - IGNORE)
        if missing:
            bad += 1
            print(f"[FAIL] {table}: 采集器要写但表里没有 → {missing}")
        if extra:
            print(f"[warn] {table}: 表里有但采集器不写（可能漏采）→ {extra}")
        if not missing:
            print(f"[ok]   {table}: 清单 {len(cols)} 列全部存在")
    conn.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
