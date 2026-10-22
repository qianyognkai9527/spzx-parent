#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷单候选: 淘宝订单 ∈ order_info(platform_type=1) 但 ∉ order_source_relation.order_no。

纯 DB 只读, 不写 brush_order(阶段一只出清单)。
跑法: automation/venv/bin/python tb-auto/detect_brush_orders.py --from 2024-10-01 --to 2026-09-30

⚠ 覆盖边界(2026-10-12 实测): order_source_relation 的 platform_type=1 数据只覆盖
  2026-02-11 起到当前(1688 ISV 工作台对更早的行「计数但不渲染」)。因此 create_time
  早于 2026-02-11 的订单会被算作"候选", 但那只是"1688 无数据"、并非刷单。脚本把候选
  按 2026-02-11 切成两桶, 只有 >= 该日的那一桶才具有判定意义。

⚠ 候选天然掺入"合法非刷单": 交易关闭 / 退款 / 从未采购的订单本来就没有 1688 采购单号,
  在 order_source_relation 里查不到关联, 会被算成候选把列表撑大。故候选只是**待人工复核
  的清单**, 不是"刷单结论"; 真实判定还要看金额/买家/时间等信号, 脚本不写 brush_order。
"""
import argparse
import json
import os
import sys
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from pnl_common import brush_candidates, connect_db, log  # noqa: E402

# 1688 关联数据的起始边界(此前 order_source_relation 无数据, 候选多属"无数据")。
COVERAGE_START = "2026-02-11"


def _amt(v):
    return v if isinstance(v, Decimal) else (Decimal(str(v)) if v is not None else Decimal("0"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--to", dest="dto", default="2026-09-30")
    ap.add_argument("--out", default=os.path.join(BASE, "brush_candidates.jsonl"))
    a = ap.parse_args()
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT o.order_no, o.create_time, o.total_amount, o.order_status, o.remark "
                "FROM order_info o WHERE o.platform_type=1 AND o.is_deleted=0 "
                "AND o.create_time >= %s AND o.create_time < DATE_ADD(%s, INTERVAL 1 DAY)",
                (a.dfrom, a.dto))
            orders = [{"order_no": r[0], "create_time": str(r[1]), "total_amount": r[2],
                       "order_status": r[3], "remark": r[4]} for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT order_no FROM order_source_relation "
                        "WHERE platform_type=1 AND is_deleted=0")
            related = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    cand = brush_candidates(orders, related)
    with open(a.out, "w", encoding="utf-8") as f:
        for c in cand:
            amt = c["total_amount"]
            f.write(json.dumps({**c, "total_amount": str(amt) if isinstance(amt, Decimal) else amt},
                               ensure_ascii=False) + "\n")

    amt_sum = sum((_amt(c["total_amount"]) for c in cand), Decimal("0"))
    old = [c for c in cand if c["create_time"] < COVERAGE_START]
    new = [c for c in cand if c["create_time"] >= COVERAGE_START]
    old_amt = sum((_amt(c["total_amount"]) for c in old), Decimal("0"))
    new_amt = sum((_amt(c["total_amount"]) for c in new), Decimal("0"))

    log(f"淘宝订单 {len(orders)}, 有 1688 关联 {len(related)}, 刷单候选 {len(cand)} "
        f"(候选金额合计 {amt_sum})")
    log("⚠ 候选含 交易关闭/退款/从未采购 的订单(本无 1688 采购单号), 只是待复核清单, 非刷单结论")
    log(f"⚠ 1688 关联仅覆盖 {COVERAGE_START} 起; 此前候选多为“无数据”, 非刷单, 勿据此判定")
    log(f"  候选分桶: < {COVERAGE_START}: {len(old)} 笔 / 金额 {old_amt}（不可信, 仅无数据）")
    log(f"            >= {COVERAGE_START}: {len(new)} 笔 / 金额 {new_amt}（可判定区间）")
    log(f"清单: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
