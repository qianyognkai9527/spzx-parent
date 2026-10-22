#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""年度真实盈亏报表（默认 2026）——把 1688 采购成本逐单配到淘宝有效订单。

配对逻辑（确定性、可解释）:
  1) offer→item_id 映射: order_source_relation×order_item(订单时点) ∪ ISV商品管理jsonl(现绑定,
     --isv-map, 默认 ../sourcing/isv_offer_taobao_map.jsonl);
  2) 每张采购单(entries 里带 offer+qty) 找 同 item_id 且 下单时间 ∈ [采购-1天, 采购+10天] 的淘宝单,
     按时间最近优先、受采购件数上限约束, 把 采购金额/件数 均摊到配到的单;
  3) 配不到淘宝单的采购 → 未归属成本(照计); 配不到采购的淘宝有效单 → 刷单嫌疑(刷单规则②落地)。

口径: 采购成本只计 **交易成功+在途**。交易关闭=钱已退回(用户 2026-10-13 确认), 不算成本。
跑法: automation/venv/bin/python tb-auto/pnl_2026_report.py [--from 2026-01-01] [--csv /tmp/pnl_2026.csv]
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from pnl_common import connect_db, log, merge_offer_items  # noqa: E402


def dt(s):
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S") if s else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2026-01-01")
    ap.add_argument("--to", dest="dto", default=None)
    ap.add_argument("--csv", default="/tmp/pnl_2026.csv")
    ap.add_argument("--isv-map", default=os.path.join(BASE, "..", "sourcing", "isv_offer_taobao_map.jsonl"),
                    help="ISV商品管理 (淘宝itemId,1688offerId) 映射 jsonl")
    ap.add_argument("--purchase-window-days", type=int, default=10,
                    help="淘宝下单后多少天内的采购算这单的(默认10)")
    a = ap.parse_args()
    import time
    dto = a.dto or time.strftime("%Y-%m-%d")
    D = Decimal

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tb_order_id FROM brush_order WHERE platform_type=1")
            brush = {r[0] for r in cur.fetchall() if r[0]}
            # offer → item_id 映射: OSR(订单时点) ∪ ISV商品管理jsonl(现绑定)
            cur.execute("""
                SELECT DISTINCT s.source_product_id, i2.item_id
                FROM order_source_relation s
                JOIN order_info o2 ON o2.order_no=s.order_no AND o2.platform_type=1
                JOIN order_item i2 ON i2.order_id=o2.id
                WHERE s.platform_type=1 AND s.source_product_id IS NOT NULL AND s.source_product_id<>''
                  AND i2.item_id IS NOT NULL AND i2.item_id<>''""")
            osr_pairs = [(str(r[0]), r[1]) for r in cur.fetchall()]
            jsonl_pairs = []
            if os.path.exists(a.isv_map):
                with open(a.isv_map, encoding="utf-8") as f:
                    for line in f:
                        try:
                            r = json.loads(line)
                        except Exception:
                            continue
                        if r.get("offer_id") and r.get("taobao_item_id"):
                            jsonl_pairs.append((str(r["offer_id"]), str(r["taobao_item_id"])))
            offer2items, map_conflicts = merge_offer_items(osr_pairs, jsonl_pairs)
            log(f"映射: OSR {len(osr_pairs)} 对 + ISV商品管理 {len(jsonl_pairs)} 对 → offer {len(offer2items)} 个"
                f" / 冲突(同offer多item,全保留) {len(map_conflicts)}")
            # 淘宝有效单 (2026 窗口): 付费单 或 关闭但有退款(退款大头在这)
            cur.execute("""
                SELECT o.order_no, i.item_id, i.product_title, o.total_amount, o.order_status, o.create_time
                FROM order_item i JOIN order_info o ON o.id=i.order_id
                WHERE o.platform_type=1 AND o.is_deleted=0
                  AND (o.order_status IN (1,2,3) OR o.order_no IN
                       (SELECT order_no FROM refund_order WHERE platform_type=1 AND status='退款成功'))
                  AND o.create_time>=%s AND o.create_time<DATE_ADD(%s, INTERVAL 1 DAY)""",
                    (a.dfrom, dto))
            orders = cur.fetchall()
            # 退款(成功) 按单
            cur.execute("""SELECT order_no, SUM(refund_amount) FROM refund_order
                           WHERE platform_type=1 AND status='退款成功'
                           GROUP BY order_no""")
            refund_by_order = {r[0]: D(str(r[1] or 0)) for r in cur.fetchall()}
            # 采购单
            cur.execute("""SELECT order_no, gmt_create, status_label, sum_payment, carriage,
                                  (gmt_payment IS NOT NULL) paid, entries_json
                           FROM purchase_order_1688
                           WHERE gmt_create>=%s AND gmt_create<DATE_ADD(%s, INTERVAL 1 DAY)
                           ORDER BY gmt_create""", (a.dfrom, dto))
            purchases = cur.fetchall()
            # 推广
            cur.execute("SELECT ROUND(SUM(charge),2) FROM promo_cost_daily WHERE stat_date>=%s", (a.dfrom,))
            promo = D(str(cur.fetchone()[0] or 0))
    finally:
        conn.close()

    # ---- 淘宝侧 ----
    valid = {}      # order_no -> dict
    for ono, item_id, title, amt, st, ct in orders:
        if ono in brush or ono in valid:
            continue
        valid[ono] = {"item_id": item_id, "title": title, "pay": D(str(amt or 0)),
                      "refund": refund_by_order.get(ono, D(0)), "create": dt(str(ct)),
                      "cost": D(0), "matched": False}
    # ---- 采购侧 ----
    purch = []
    for ono, gc, stl, sp, ca, paid, ej in purchases:
        amt = D(str(sp or 0)) + D(str(ca or 0))
        ents = json.loads(ej or "[]")
        offers = [str(e.get("sourceId")) for e in ents if e.get("sourceId")]
        try:
            qty = sum(int(float(e.get("quantity") or 0)) for e in ents) or 1
        except Exception:
            qty = 1
        purch.append({"order_no": ono, "time": dt(str(gc)), "status": stl, "paid": bool(paid),
                      "amount": amt, "qty": qty, "offers": offers})
    live = [p for p in purch if p["status"] in ("交易成功", "待发货", "待收货")]
    closed = [p for p in purch if p["status"] == "交易关闭"]
    closed_paid_amt = sum((p["amount"] for p in closed if p["paid"]), D(0))

    # ---- 配对 ----
    item_orders = {}
    for ono, v in valid.items():
        if v["item_id"]:
            item_orders.setdefault(v["item_id"], []).append(ono)
    unattributed = D(0)
    matched_purch = 0
    for p in live:
        cand = []
        seen_items = set()
        for off in p["offers"]:
            for it in offer2items.get(off, []):
                if it in seen_items:
                    continue
                seen_items.add(it)
                for ono in item_orders.get(it, []):
                    v = valid[ono]
                    if v["matched"]:
                        continue
                    lag = (p["time"] - v["create"]).total_seconds() / 86400.0
                    if -1 <= lag <= a.purchase_window_days:
                        cand.append((abs(lag), ono))
        cand.sort()
        per = (p["amount"] / p["qty"]).quantize(D("0.01")) if p["qty"] else p["amount"]
        took = 0
        for _, ono in cand:
            if took >= p["qty"]:
                break
            valid[ono]["cost"] += per
            valid[ono]["matched"] = True
            took += 1
        if took:
            matched_purch += 1
        unattributed += p["amount"] - per * took

    # ---- 汇总 ----
    tot_pay = sum((v["pay"] for v in valid.values()), D(0))
    tot_ref = sum((v["refund"] for v in valid.values()), D(0))
    tot_cost = sum((v["cost"] for v in valid.values()), D(0))
    live_amt = sum((p["amount"] for p in live), D(0))
    suspects = [(o, v) for o, v in valid.items() if not v["matched"]]
    sus_pay = sum((v["pay"] for _, v in suspects), D(0))
    sus_ref = sum((v["refund"] for _, v in suspects), D(0))
    real_a = tot_pay - tot_ref - live_amt - promo   # 交易关闭=钱已退回(用户 2026-10-13 确认)

    log(f"窗口 {a.dfrom}~{dto}: 有效单 {len(valid)} / 采购(成功+在途) {len(live)} 张 ¥{live_amt} "
        f"(配到单 {matched_purch} 张, 未归属 ¥{unattributed}) / 关闭 {len(closed)} 张 ¥{closed_paid_amt}(已退款,不算成本)")
    log(f"毛利口径: 支付 ¥{tot_pay} − 退款 ¥{tot_ref} = ¥{tot_pay - tot_ref}")
    log(f"真实盈亏(交易关闭=钱已退回, 用户已确认): {tot_pay - tot_ref} − 采购 {live_amt} − 推广 {promo} = ¥{real_a}")
    log(f"刷单嫌疑(有效单但配不到采购, 仅供人工核查, 受映射稀疏影响偏大): {len(suspects)} 单, 支付 ¥{sus_pay}, 退款 ¥{sus_ref}")

    # ---- 明细 ----
    rows = sorted(valid.items(), key=lambda kv: (kv[1]["pay"] - kv[1]["refund"] - kv[1]["cost"]), reverse=True)
    with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["订单号", "商品id", "支付", "退款", "采购成本", "单笔盈亏", "有采购匹配", "商品"])
        for ono, v in rows:
            w.writerow([ono, v["item_id"] or "", v["pay"], v["refund"], v["cost"],
                        v["pay"] - v["refund"] - v["cost"], "是" if v["matched"] else "否",
                        (v["title"] or "")[:30]])
    log(f"明细 CSV: {a.csv} ({len(rows)} 行)")
    shown = rows[:15]
    log(f"{'订单号':<20}{'支付':>9}{'退款':>9}{'成本':>8}{'盈亏':>9}  商品")
    for ono, v in shown:
        log(f"{ono:<20}{v['pay']:>9}{v['refund']:>9}{v['cost']:>8}{v['pay']-v['refund']-v['cost']:>9}  {(v['title'] or '')[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
