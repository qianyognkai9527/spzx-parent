#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""订单聚合 → 真实出单榜 (2026-09-08)

数据源: sourcing/orders_report.xlsx (千牛宝贝销售明细报表导出, 近3个月)
用途: 从历史订单找「低流量仍出单」的转化体质款, 给付费测款候选池排序。

用法: orders_rank.py [--file FILE] [--top 30]
输出: 控制台摘要 + orders_rank_report.md
"""
import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime

import openpyxl

DEFAULT_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/orders_report.xlsx"
OUT_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/orders_rank_report.md"

# 有效成交状态(计入爆品判定); 交易关闭/退款成功单独统计
ACTIVE_STATUSES = ("交易成功", "买家已付款", "已发货", "等待卖家发货", "卖家已发货")


def fmt_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--days", type=int, default=0,
                    help="只看最近N天的订单(按创建时间), 默认0=全部")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.file, read_only=True, data_only=True)
    ws = wb.active
    hdr = [c.value for c in next(ws.iter_rows())]
    col = {h: i for i, h in enumerate(hdr)}

    from datetime import timedelta
    cutoff = (datetime.combine(date.today(), datetime.min.time())
              - timedelta(days=args.days)) if args.days else None

    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        status = r[col["订单状态"]] or ""
        ct = fmt_dt(r[col["订单创建时间"]])
        if cutoff and (not ct or ct < cutoff):
            continue
        rows.append(dict(
            sub_id=r[col["子订单编号"]],
            title=r[col["商品标题"]] or "",
            price=float(r[col["商品价格"]] or 0),
            qty=int(r[col["购买数量"]] or 1),
            attr=r[col["商品属性"]] or "",
            status=status,
            pay_amt=float(r[col["买家实付金额"]] or 0),
            refund=r[col["退款状态"]] or "",
            refund_amt=float(r[col["退款金额"]] or 0) if isinstance(r[col["退款金额"]], (int, float)) else 0,
            create_time=ct,
            pay_time=fmt_dt(r[col["订单付款时间"]]),
            item_id=r[col["商品ID"]],
        ))
    wb.close()

    effective = [r for r in rows if r["status"] != "交易关闭"]

    print(f"总子订单 {len(rows)} | 有效 {len(effective)} | 交易关闭 {len(rows)-len(effective)}")

    # 商品维度聚合(有效订单)
    prod = defaultdict(lambda: dict(title="", qty=0, orders=0, pay=0.0,
                                    first=None, last=None, closed=0, statuses=defaultdict(int)))
    for r in effective:
        key = str(r["item_id"])
        p = prod[key]
        p["title"] = r["title"]
        p["qty"] += r["qty"]
        p["orders"] += 1
        p["pay"] += r["pay_amt"]
        if r["create_time"]:
            if not p["first"] or r["create_time"] < p["first"]:
                p["first"] = r["create_time"]
            if not p["last"] or r["create_time"] > p["last"]:
                p["last"] = r["create_time"]
    for r in rows:
        if r["status"] == "交易关闭":
            prod[str(r["item_id"])]["closed"] += 1

    # SKU 维度(商品属性 颜色/尺码)
    sku = defaultdict(lambda: defaultdict(int))
    for r in effective:
        for seg in r["attr"].split(";"):
            seg = seg.strip()
            if not seg:
                continue
            sku[str(r["item_id"])][seg] += r["qty"]

    ranked = sorted(prod.values(), key=lambda p: (p["orders"], p["pay"]), reverse=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pay = sum(p["pay"] for p in prod.values())
    id_by_title = {}
    for r in effective:
        id_by_title.setdefault(r["title"], str(r["item_id"]))
    today = date.today()

    lines = [
        f"# 订单出单榜 ({now}, 近{args.days or '3'}个月窗口)" if args.days else f"# 订单出单榜 ({now}, 近3个月)",
        "",
        f"总子订单 {len(rows)} | 有效成交 {len(effective)} (关闭 {len(rows)-len(effective)}) | 有效实收 ¥{total_pay:.2f}",
        "",
        "## 有效成交 Top (转化体质款)",
        "",
        "| # | 商品ID | 出单数 | 件数 | 实收¥ | 首单 | 末单 | 活跃 | 关闭单 | 标题 |",
        "|---|--------|--------|------|-------|------|------|------|--------|------|",
    ]
    for i, p in enumerate(ranked[:args.top], 1):
        last_d = p["last"].date() if p["last"] else None
        active_days = (today - last_d).days if last_d else 999
        active_flag = "🔥近30天" if active_days <= 30 else ("近90天" if active_days <= 90 else "已凉")
        first_s = p["first"].strftime("%m-%d") if p["first"] else "-"
        last_s = p["last"].strftime("%m-%d") if p["last"] else "-"
        iid = id_by_title.get(p["title"], "?")
        lines.append(
            f"| {i} | {iid} | {p['orders']} | {p['qty']} | {p['pay']:.2f} "
            f"| {first_s} | {last_s} | {active_flag} | {p['closed']} | {p['title'][:34]} |")

    lines += ["", "## 热销款 SKU 分布 (颜色/尺码)", ""]
    for i, p in enumerate(ranked[:8], 1):
        iid = id_by_title.get(p["title"], "?")
        skus = sorted(sku[iid].items(), key=lambda x: -x[1])[:5]
        sku_s = "; ".join(f"{k}×{n}" for k, n in skus)
        lines.append(f"**{i}. {p['title'][:30]}** ({p['orders']}单): {sku_s}")

    report = "\n".join(lines)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    # 机器可读 JSON (供 hot_rank.py 融合)
    import json as _json
    out_json = {id_by_title.get(p["title"], "?"): dict(
        title=p["title"], orders=p["orders"], qty=p["qty"], pay=round(p["pay"], 2),
        last=p["last"].strftime("%Y-%m-%d") if p["last"] else "",
        first=p["first"].strftime("%Y-%m-%d") if p["first"] else "",
        closed=p["closed"]) for p in ranked}
    _json.dump(out_json, open("/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/orders_rank.json", "w"),
               ensure_ascii=False, indent=1)
    print(f"→ {OUT_FILE} + orders_rank.json ({len(out_json)}款)")
    print(f"有效款数: {len(prod)}")
    for i, p in enumerate(ranked[:10], 1):
        last_d = p["last"].date() if p["last"] else None
        active_days = (today - last_d).days if last_d else 999
        flag = "🔥" if active_days <= 30 else ("·" if active_days <= 90 else "☠")
        print(f"  {i}. [{flag}] {p['orders']}单/¥{p['pay']:.0f} {p['title'][:30]}")


if __name__ == "__main__":
    main()
