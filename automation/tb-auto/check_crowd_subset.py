#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子集校验: 对每个 (item_id, campaign_id, stat_date), Σ人群 click 应 <= 单元 click。

超了说明平台把一次点击记到了多个人群实例(重复计数), 页面占比会 >100%, 必须人工看。
一次性/周期性自查脚本, 不写库。跑法:
  automation/venv/bin/python check_crowd_subset.py --from 2026-10-01 --to 2026-10-11
"""
import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cron_batch import DB_CONFIG  # noqa: E402
import pymysql  # noqa: E402

SQL = """
SELECT c.item_id, c.campaign_id, c.stat_date, c.crowd_click, i.item_click
FROM (SELECT item_id, campaign_id, stat_date, SUM(click) AS crowd_click
      FROM promo_cost_item_daily
      WHERE dimension = 'crowd' AND stat_date BETWEEN %s AND %s
      GROUP BY item_id, campaign_id, stat_date) c
JOIN (SELECT item_id, campaign_id, stat_date, SUM(click) AS item_click
      FROM promo_cost_item_daily
      WHERE dimension = 'item' AND stat_date BETWEEN %s AND %s
      GROUP BY item_id, campaign_id, stat_date) i
  ON i.item_id = c.item_id AND i.campaign_id = c.campaign_id AND i.stat_date = c.stat_date
WHERE c.crowd_click > i.item_click
ORDER BY (c.crowd_click - i.item_click) DESC
LIMIT %s
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom",
                    default=(date.today() - timedelta(days=14)).isoformat())
    ap.add_argument("--to", dest="dto", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()

    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(SQL, (a.dfrom, a.dto, a.dfrom, a.dto, a.limit))
            bad = cur.fetchall()
    finally:
        conn.close()

    if not bad:
        print(f"OK: {a.dfrom}~{a.dto} 无「人群 click > 单元 click」的 (item,campaign,date)")
        return 0
    print(f"!! {len(bad)} 处人群点击超过单元点击（疑似重复计数）:")
    for item_id, cid, day, cc, ic in bad:
        print(f"  {day} 计划{cid} 宝贝{item_id}: 人群{cc} > 单元{ic}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
