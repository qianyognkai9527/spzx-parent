#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把成交侧四个字段从 extra_json 回填到 sycm_item_effect_history 的独立列。

为什么能回填而不用重采：采集器一直把生意参谋返回的整条 item 原样存进 extra_json，
缺的只是"没摊平成列"。所以历史快照里的下单/支付/退款数据本来就在库里。

字段口径与 sycm_item_snapshot.parse_items 用同一个 _opt_num，避免两套映射漂移：
  pay_items   ← payItmCnt      支付件数（算货成本用件数；pay_byrs 是人数）
  order_amt   ← crtAmt         下单金额（含未付款）
  order_items ← crtItmQty      下单件数
  refund_amt  ← sucRefundAmt   成功退款金额
键不存在 → 留 NULL，不写 0：0 会被下游读成"零成交"，而真相是"那天没这个字段"。

用法:
  backfill_sycm_money_fields.py            只补四个列全为 NULL 的行
  backfill_sycm_money_fields.py --recompute  全量按 extra_json 重算（改了映射后用）
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql  # noqa: E402
from sycm_item_snapshot import DB, _opt_num  # noqa: E402

FIELDS = (("pay_items", "payItmCnt", True),
          ("order_amt", "crtAmt", False),
          ("order_items", "crtItmQty", True),
          ("refund_amt", "sucRefundAmt", False))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def extract(extra_json):
    """从原始 JSON 取四列；JSON 坏了/截断了返回 None（调用方跳过，不写脏值）"""
    if not extra_json:
        return None
    try:
        it = json.loads(extra_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(it, dict):
        return None
    return tuple(_opt_num(it, key, as_int) for _, key, as_int in FIELDS)


def plan_sql(recompute):
    cols = ", ".join(c for c, _, _ in FIELDS)
    if recompute:
        return f"SELECT id, extra_json FROM sycm_item_effect_history WHERE extra_json IS NOT NULL", cols
    # 只要有一列已经填过就算处理过，避免每次全表扫
    nulls = " AND ".join(f"{c} IS NULL" for c, _, _ in FIELDS)
    return f"SELECT id, extra_json FROM sycm_item_effect_history WHERE extra_json IS NOT NULL AND ({nulls})", cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true", help="忽略已填的值，按 extra_json 全量重算")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    sql, _ = plan_sql(args.recompute)
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    update = ("UPDATE sycm_item_effect_history SET " +
              ", ".join(f"{c}=%s" for c, _, _ in FIELDS) + " WHERE id=%s")

    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            log(f"待处理 {len(rows)} 行")
            batch, parsed, skipped = [], 0, 0
            for rid, extra in rows:
                vals = extract(extra)
                if vals is None:
                    skipped += 1
                    continue
                batch.append(vals + (rid,))
                if len(batch) >= 500:
                    cur.executemany(update, batch)
                    conn.commit()
                    batch = []
            if batch:
                cur.executemany(update, batch)
                conn.commit()
            for col, key, _ in FIELDS:
                cur.execute(f"SELECT COUNT({col}) FROM sycm_item_effect_history")
                filled = cur.fetchone()[0]
                cur.execute(f"SELECT SUM({col} IS NOT NULL AND {col} <> 0) "
                            f"FROM sycm_item_effect_history")
                nonzero = cur.fetchone()[0] or 0
                log(f"  {col:12} ← {key:14} 非NULL {filled} 行，其中 >0 {int(nonzero)} 行")
        log(f"完成: JSON 不可解析而跳过 {skipped} 行")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
