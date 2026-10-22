#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""商品级退款绩效表(只读, 按权威 item_id 归集)。

列: 商品id / 有效订单数 / 退款订单数 / 未发货秒退订单数 / 退款率 / 去除秒退退款率 /
    支付金额 / 退款金额 / 秒退金额 / 利润(支付-退款 毛利)。

归集键 = 权威 item_id, 取值优先级(每个订单一条):
  1) order_item.item_id  —— 来自 tradeSnap 的 itemSnapDO.itemId(权威, collect_order_item_ids.py 回填)
  2) refund_order.item_id —— 该单的退款记录(权威, 覆盖「无快照但退款」的关闭单)
  3) 标题→item_id 映射     —— 由 1)+2) 的权威对 + platform_product 兜底(改标题的商品靠此对齐)
绝不单独依赖标题: 标题只做上面两项都取不到时的兜底, 且兜底来源本身也是权威对。

口径(用户确认):
  有效订单 = 付过钱的单(排除刷单): order_status∈{1,2,3} 或该单有退款(按 order_no);
  退款单  = refund_order status='退款成功'(distinct order_no, 剔刷单);
  秒退    = 该单有 after_sale_type='未发货退款' 且 '退款成功';
  退款率  = 退款单/有效单; 去秒退率=(退款单-秒退)/(有效单-秒退);
  利润    = 支付金额 - 退款金额(毛利, 不含成本/推广)。

跑法: automation/venv/bin/python tb-auto/refund_product_report.py --from 2024-10-01
"""
import argparse
import csv
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from pnl_common import connect_db, log  # noqa: E402


def build_title_map(cur):
    """标题→item_id: 权威对(order_item / refund_order) 优先, platform_product 兜底。"""
    m = {}
    cur.execute("SELECT product_title, item_id FROM refund_order "
                "WHERE platform_type=1 AND item_id IS NOT NULL AND product_title IS NOT NULL")
    for t, iid in cur.fetchall():
        m[t] = iid
    cur.execute("SELECT product_title, item_id FROM order_item "
                "WHERE item_id IS NOT NULL AND item_id<>'' AND product_title IS NOT NULL")
    for t, iid in cur.fetchall():
        m.setdefault(t, iid)
    cur.execute("SELECT title, code FROM platform_product WHERE platform_type=1")
    for t, code in cur.fetchall():
        m.setdefault(t, code)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--to", dest="dto", default=None)
    ap.add_argument("--out", default="/tmp/refund_by_product.csv")
    ap.add_argument("--top", type=int, default=0)
    a = ap.parse_args()
    import time
    dto = a.dto or time.strftime("%Y-%m-%d")
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tb_order_id FROM brush_order WHERE platform_type=1")
            brush = {r[0] for r in cur.fetchall() if r[0]}
            title2id = build_title_map(cur)

            # 订单 (含 item_id 与标题)
            cur.execute("""
                SELECT o.order_no, oi.item_id, oi.product_title, o.total_amount, o.order_status
                FROM order_item oi JOIN order_info o ON o.id=oi.order_id
                WHERE o.platform_type=1 AND o.is_deleted=0
                  AND o.create_time>=%s AND o.create_time<DATE_ADD(%s, INTERVAL 1 DAY)""",
                        (a.dfrom, dto))
            orders = cur.fetchall()

            # 退款 (成功单)
            cur.execute("""
                SELECT order_no, item_id, product_title, after_sale_type, refund_amount
                FROM refund_order
                WHERE platform_type=1 AND status='退款成功'""")
            refunds = cur.fetchall()
    finally:
        conn.close()

    # 按 order_no 聚合退款(成功)
    ref_orders = set()
    sec_orders = set()
    ref_amt_by_order, sec_amt_by_order, refund_item = {}, {}, {}
    for ono, iid, title, ty, amt in refunds:
        if not ono or ono in brush:
            continue
        ref_orders.add(ono)
        refund_item.setdefault(ono, iid)
        ref_amt_by_order[ono] = ref_amt_by_order.get(ono, 0.0) + float(amt or 0)
        if (ty or "") == "未发货退款":
            sec_orders.add(ono)
            sec_amt_by_order[ono] = sec_amt_by_order.get(ono, 0.0) + float(amt or 0)

    # 有效订单 → item_id(权威优先) + 归集键
    valid_key, valid_cnt, pay_amt, disp_title = {}, {}, {}, {}
    unmapped = {}
    src_stat = {"order_item": 0, "refund": 0, "title": 0, "none": 0}
    for ono, oi_item, title, amt, st in orders:
        if ono in brush:
            continue
        valid = (st in (1, 2, 3)) or (ono in ref_orders)
        if not valid or ono in valid_key:
            continue
        if oi_item:
            iid, src = oi_item, "order_item"
        elif refund_item.get(ono):
            iid, src = refund_item[ono], "refund"
        elif title2id.get(title):
            iid, src = title2id[title], "title"
        else:
            iid, src = None, "none"
        src_stat[src] += 1
        k = iid or ("T:" + (title or ""))
        if iid is None:
            unmapped[title or "(无标题)"] = unmapped.get(title or "(无标题)", 0) + 1
        valid_key[ono] = k
        valid_cnt[k] = valid_cnt.get(k, 0) + 1
        pay_amt[k] = pay_amt.get(k, 0.0) + float(amt or 0)
        disp_title.setdefault(k, title)

    # 退款指标(归到订单同一键 → 分子必⊆分母)
    ref_cnt, sec_cnt, ref_amt, sec_amt = {}, {}, {}, {}
    dropped_refunds = 0
    for ono in ref_orders:
        k = valid_key.get(ono)
        if k is None:
            dropped_refunds += 1     # 退款单不在订单采集窗口内
            continue
        ref_cnt.setdefault(k, set()).add(ono)
        ref_amt[k] = ref_amt.get(k, 0.0) + ref_amt_by_order.get(ono, 0.0)
        if ono in sec_orders:
            sec_cnt.setdefault(k, set()).add(ono)
            sec_amt[k] = sec_amt.get(k, 0.0) + sec_amt_by_order.get(ono, 0.0)

    keys = set(valid_cnt) | set(ref_cnt)
    rows = []
    for k in keys:
        v = valid_cnt.get(k, 0)
        r = len(ref_cnt.get(k, set()))
        sec = len(sec_cnt.get(k, set()))
        pay = pay_amt.get(k, 0.0)
        ra = ref_amt.get(k, 0.0)
        sa = sec_amt.get(k, 0.0)
        rate = (r / v * 100) if v else 0.0
        rate2 = ((r - sec) / (v - sec) * 100) if (v - sec) > 0 else 0.0
        rows.append((k, v, r, sec, rate, rate2, pay, ra, sa, pay - ra, disp_title.get(k, "")))
    rows.sort(key=lambda x: -x[1])

    log(f"有效订单 item_id 来源: 快照 {src_stat['order_item']} / 退款 {src_stat['refund']} / "
        f"标题兜底 {src_stat['title']} / 未映射 {src_stat['none']}"
        + (f" | 窗口外退款单 {dropped_refunds}" if dropped_refunds else ""))
    if unmapped:
        top_un = sorted(unmapped.items(), key=lambda x: -x[1])[:8]
        log(f"未映射标题(前 8): {top_un}")
    log(f"{'商品id':<14}{'有效':>5}{'退款':>5}{'秒退':>5}{'退款率':>8}{'去秒退率':>9}{'支付金额':>11}{'退款金额':>10}{'秒退金额':>10}{'利润':>11}  商品")
    shown = rows if not a.top else rows[:a.top]
    tot = [0, 0, 0, 0.0, 0.0, 0.0, 0.0]
    for k, v, r, sec, rate, rate2, pay, ra, sa, prof, title in rows:
        tot[0] += v; tot[1] += r; tot[2] += sec; tot[3] += pay; tot[4] += ra; tot[5] += sa; tot[6] += prof
    for k, v, r, sec, rate, rate2, pay, ra, sa, prof, title in shown:
        iid = k if not k.startswith("T:") else ""
        log(f"{str(iid):<14}{v:>5}{r:>5}{sec:>5}{rate:>7.1f}%{rate2:>8.1f}%{pay:>11.2f}{ra:>10.2f}{sa:>10.2f}{prof:>11.2f}  {(title or '')[:22]}")
    log(f"合计(全部 {len(rows)} 商品): 有效 {tot[0]} / 退款 {tot[1]} / 秒退 {tot[2]} / 支付 {tot[3]:.2f} / "
        f"退款 {tot[4]:.2f} / 秒退 {tot[5]:.2f} / 利润(支付-退款) {tot[6]:.2f}")

    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["商品id", "有效订单数", "退款订单数", "未发货秒退订单数", "退款率%", "去除秒退退款率%",
                    "支付金额", "退款金额", "秒退金额", "利润", "商品标题"])
        for k, v, r, sec, rate, rate2, pay, ra, sa, prof, title in rows:
            iid = k if not k.startswith("T:") else ""
            w.writerow([iid, v, r, sec, round(rate, 1), round(rate2, 1),
                        round(pay, 2), round(ra, 2), round(sa, 2), round(prof, 2), title])
    log(f"CSV: {a.out} ({len(rows)} 行)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
