#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""退款只读报告: 按月退款率/额、按售后类型、按商品 top 退款。纯 DB, 不写库。

刷单剔除(默认开启, --include-brush 关闭): 满足任一即判刷单并剔除
  ① 订单号在 brush_order 台账(platform_type=1);
  ② 订单在 1688 关联覆盖期内(>= min(order_source_relation.order_time))但无任何 1688 关联。
  (2023~2026 早于 1688 覆盖期的订单无法用 ② 判定, 只能用 ①。)

退款率定义: 分子 = 申请月退款单数(按 refund_order.apply_time),
分母 = 成交月订单数(按 order_info.create_time) —— 非订单 cohort 率, 可能 >100%。

跑法: automation/venv/bin/python tb-auto/refund_report.py --from 2024-10-01 --to 2026-09-30
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from pnl_common import connect_db, log  # noqa: E402


def brush_order_nos(cur):
    """刷单订单号集合: ① brush_order 台账 ② 1688 覆盖期内无关联的订单。"""
    cur.execute("SELECT tb_order_id FROM brush_order WHERE platform_type=1")
    s = {r[0] for r in cur.fetchall() if r[0]}
    cur.execute("SELECT MIN(order_time) FROM order_source_relation WHERE platform_type=1")
    since = cur.fetchone()[0]
    if since:
        cur.execute("""
            SELECT o.order_no FROM order_info o
            WHERE o.platform_type=1 AND o.is_deleted=0 AND o.create_time>=%s
              AND o.order_no NOT IN (SELECT order_no FROM order_source_relation WHERE platform_type=1)""",
                    (since,))
        s |= {r[0] for r in cur.fetchall() if r[0]}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--to", dest="dto", default="2026-09-30")
    ap.add_argument("--include-brush", action="store_true", help="不剔除刷单单(看原始)")
    a = ap.parse_args()
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            brush = set() if a.include_brush else brush_order_nos(cur)
            cur.execute("""
                SELECT order_no, DATE_FORMAT(apply_time,'%%Y-%%m'), after_sale_type,
                       refund_amount, product_title, status
                FROM refund_order
                WHERE platform_type=1 AND apply_time>=%s AND apply_time<DATE_ADD(%s, INTERVAL 1 DAY)""",
                        (a.dfrom, a.dto))
            all_rows = cur.fetchall()
            dropped = [r for r in all_rows if r[0] in brush]
            rows = [r for r in all_rows if r[0] not in brush]
            # 退款关闭 = 申请被拒/撤销, 没真退钱 → 金额/退款率只算"退款成功"
            done = [r for r in rows if (r[5] or "") == "退款成功"]
            closed = [r for r in rows if (r[5] or "") != "退款成功"]
            log(f"窗口 {a.dfrom}~{a.dto}; 退款记录 {len(all_rows)} 笔, "
                f"剔除刷单 {len(dropped)} 笔"
                + (" (--include-brush 未剔除)" if a.include_brush else "")
                + f"; 计 {len(rows)} 笔 (退款成功 {len(done)} / 关闭·未退 {len(closed)})")

            # 按月(仅退款成功计额)
            by_month = {}
            for _, m, _, amt, _t, _s in done:
                c, s = by_month.get(m, (0, 0))
                by_month[m] = (c + 1, s + float(amt or 0))
            cur.execute("""
                SELECT DATE_FORMAT(create_time,'%%Y-%%m') m, COUNT(*) FROM order_info
                WHERE platform_type=1 AND is_deleted=0
                  AND create_time>=%s AND create_time<DATE_ADD(%s, INTERVAL 1 DAY)
                GROUP BY m""", (a.dfrom, a.dto))
            orders = {r[0]: r[1] for r in cur.fetchall()}

            log("== 按月：实退单 / 实退额 / 成交单 / 退款率 (仅退款成功, 已剔刷单) ==")
            for m in sorted(set(orders) | set(by_month)):
                oc = orders.get(m, 0)
                rc, ra = by_month.get(m, (0, 0.0))
                rate = (rc / oc * 100) if oc else 0
                log(f"  {m}: 成交单 {oc}  实退单 {rc}  实退额 {ra:.2f}  退款率 {rate:.1f}%")

            log("== 按售后类型 (成功=真退钱 / 关闭=申请未退) ==")
            by_type = {}
            for _, _, t, amt, _tt, s in rows:
                k = t or "(未知)"
                sc, sm, cc, cm = by_type.get(k, (0, 0.0, 0, 0.0))
                if (s or "") == "退款成功":
                    by_type[k] = (sc + 1, sm + float(amt or 0), cc, cm)
                else:
                    by_type[k] = (sc, sm, cc + 1, cm + float(amt or 0))
            for t, (sc, sm, cc, cm) in sorted(by_type.items(), key=lambda kv: -kv[1][0]):
                log(f"  {t}: 成功 {sc} 单 ¥{sm:.2f}   关闭 {cc} 单 ¥{cm:.2f}")

            log("== 按商品 top10 (按实退单数, 已剔刷单) ==")
            by_prod = {}
            for _, _, _t, amt, title, _s in done:
                if not title:
                    continue
                c, s = by_prod.get(title, (0, 0))
                by_prod[title] = (c + 1, s + float(amt or 0))
            for t, (c, s) in sorted(by_prod.items(), key=lambda kv: -kv[1][0])[:10]:
                log(f"  {c} 单 ¥{s:.2f}  {t}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
