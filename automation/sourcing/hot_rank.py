#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""爆品初筛榜单 (2026-09-07)

数据源:
  - sycm_item_effect_history (生意参谋商品效果快照, sycm_item_snapshot.py 采集)
  - taobao_isv_bind.jsonl (tbId↔srcId 映射)
  - source_product (货源销量/复购率/货源价)

模型: 潜力分 = 加购率*35 + 访客规模*20 + 加购人数*15 + 收藏*5 + 货源销量*15 + 复购率*10
档位: S=已爆信号(访客≥100且加购率≥10%) A=强潜力(加购率≥6%且访客≥30)
      B=观察(加购率≥4%或加购≥3人) C=数据不足

用法: hot_rank.py [--date-type recent7] [--top 50] [--out FILE]
"""
import argparse
import json
import math
from datetime import datetime

import pymysql

DB = dict(host="localhost", user="root", password="root123456",
          database="db_spzx", charset="utf8mb4")
BIND_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/taobao_isv_bind.jsonl"


def load_bind():
    m = {}
    try:
        with open(BIND_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    m[str(r["tbId"])] = r
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return m


def load_source_info(src_ids):
    """srcId 实为 1688 offerId, 对应 source_product.source_product_code"""
    if not src_ids:
        return {}
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(src_ids))
            cur.execute(
                f"""select source_product_code, source_product_name, sales_count,
                           repurchase_rate, source_price, category_name
                    from source_product
                    where source_product_code in ({fmt}) and is_deleted=0
                    order by sales_count desc""", list(src_ids))
            out = {}
            for r in cur.fetchall():
                code = str(r[0])
                if code in out:   # 同 offer 多行: 保留销量最高的(已排序)
                    continue
                out[code] = dict(name=r[1], sales=r[2] or 0,
                                 repurchase=float(r[3] or 0),
                                 price=float(r[4] or 0), cate=r[5])
            return out
    finally:
        conn.close()


def load_latest_snapshot(date_type):
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """select t.item_id, t.title, t.visitors, t.page_views, t.cart_users,
                          t.fav_users, t.date_range, t.snapshot_time,
                          t.cart_rate, t.pay_byrs, t.pay_amt, t.stay_sec, t.se_uv
                   from sycm_item_effect_history t
                   join (select item_id, max(id) mid from sycm_item_effect_history
                         where date_type=%s group by item_id) l
                     on l.mid = t.id""", (date_type,))
            return {str(r[0]): dict(title=r[1], visitors=r[2] or 0, pv=r[3] or 0,
                                    cart=r[4] or 0, fav=r[5] or 0,
                                    dr=r[6], snap=r[7], cart_rate=r[8] or 0,
                                    pay_byrs=r[9] or 0, pay_amt=r[10] or 0,
                                    stay=r[11] or 0, se_uv=r[12] or 0) for r in cur.fetchall()}
    finally:
        conn.close()


def load_orders():
    """订单聚合 (orders_rank.py 输出) {item_id: {...}}"""
    try:
        with open("/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/orders_rank.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def score(v):
    cart_rate = (v["cart"] / v["visitors"]) if v["visitors"] else 0
    s = 0
    s += 35 * min(cart_rate / 0.15, 1.0)                       # 加购率
    s += 20 * min(math.log10(v["visitors"] + 1) / math.log10(500), 1.0)  # 访客规模(对数)
    s += 15 * min(v["cart"] / 50, 1.0)                          # 加购人数
    s += 5 * min(v["fav"] / 30, 1.0)                            # 收藏
    src = v.get("_src") or {}
    s += 15 * min(math.log10((src.get("sales") or 0) + 1) / 4, 1.0)      # 货源销量
    s += 10 * min((src.get("repurchase") or 0) / 30.0, 1.0)     # 复购率
    # 订单实绩 (转化体质): 出单数 + 近期活跃
    od = v.get("_orders") or {}
    s += 20 * min((od.get("orders") or 0) / 10.0, 1.0)          # 出单数
    if od.get("last"):
        from datetime import date, datetime
        try:
            days = (date.today() - datetime.strptime(od["last"], "%Y-%m-%d").date()).days
            if days <= 30:
                s += 10                                # 近30天出单 = 活跃爆款加成
        except Exception:
            pass
    return round(s, 1), cart_rate


def tier(visitors, cart_users, cart_rate):
    if visitors >= 100 and cart_rate >= 0.10:
        return "S"
    if visitors >= 30 and cart_rate >= 0.06:
        return "A"
    if cart_rate >= 0.04 or cart_users >= 3:
        return "B"
    return "C"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-type", default="recent7")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--out", default="/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/hot_rank_report.md")
    args = ap.parse_args()

    bind = load_bind()
    src_info = load_source_info({b["srcId"] for b in bind.values() if b.get("srcId")})
    snap = load_latest_snapshot(args.date_type)
    orders = load_orders()

    if not snap:
        print(f"[hot_rank] {args.date_type} 无快照数据 — 先跑 sycm_item_snapshot.py")
        return

    rows = []
    for tb_id, v in snap.items():
        v["_src"] = src_info.get(str(bind.get(tb_id, {}).get("srcId")), {})
        v["_orders"] = orders.get(str(tb_id), {})
        sc, cart_rate = score(v)
        od = v["_orders"]
        rows.append(dict(tb_id=tb_id, title=v["title"], sc=sc, cart_rate=cart_rate,
                         visitors=v["visitors"], cart=v["cart"], fav=v["fav"],
                         dr=v["dr"], snap=v["snap"],
                         status=bind.get(tb_id, {}).get("tbStatus", "?"),
                         src=v["_src"], orders=od.get("orders", 0),
                         orders_pay=od.get("pay", 0), orders_last=od.get("last", "")))
    rows.sort(key=lambda r: r["sc"], reverse=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tiers = {}
    for r in rows:
        r["tier"] = tier(r["visitors"], r["cart"], r["cart_rate"])
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1

    lines = [
        f"# 爆品初筛榜 ({now}, {args.date_type}, 快照={rows[0]['snap']})",
        "",
        f"覆盖商品 {len(rows)} | 档位分布: S={tiers.get('S',0)} A={tiers.get('A',0)} "
        f"B={tiers.get('B',0)} C={tiers.get('C',0)}",
        "",
        "| # | 档 | 淘宝ID | 标题 | 状态 | 出单 | 实收¥ | 末单 | 货源销量 | 复购% | 货源价 | 潜力分 |",
        "|---|----|--------|------|------|------|-------|------|----------|-------|--------|--------|",
    ]
    for i, r in enumerate(rows[:args.top], 1):
        t = r["title"][:26]
        s = r["src"]
        lines.append(
            f"| {i} | {r['tier']} | {r['tb_id']} | {t} | {r['status']} "
            f"| {r['orders']} | {r['orders_pay']:.0f} | {r['orders_last'][5:] or '-'} "
            f"| {s.get('sales', 0)} | {s.get('repurchase', 0)} "
            f"| {s.get('price', 0)} | {r['sc']} |")

    lines += ["", "## 万相台测款候选池", ""]
    # 优先: 订单出单>0 的款(转化体质) → 其次 货源销量Top; 排序按潜力分
    cand = sorted([r for r in rows if r["orders"] > 0], key=lambda r: r["sc"], reverse=True)
    if not cand:
        cand = sorted(rows, key=lambda r: r["sc"], reverse=True)[:30]
    lines.append(f"候选池 {len(cand)} 款 (先订单出单款, 再按潜力分补足). 建议首批进万相台小额测款(每款30元×3天):")
    for r in cand[:30]:
        lines.append(f"- {r['tb_id']} 出单{r['orders']} {r['title'][:36]} "
                     f"(分{r['sc']} 末单{r['orders_last'][5:] or '-'})")

    report = "\n".join(lines)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[hot_rank] 商品{len(rows)} S={tiers.get('S',0)} A={tiers.get('A',0)} "
          f"B={tiers.get('B',0)} → {args.out}")
    for r in rows[:10]:
        print(f"  {r['tier']} 分{r['sc']:<5} 出单{r['orders']:<3} 实收{r['orders_pay']:>7.0f} "
              f"末单{r['orders_last'][5:] or '--':<5}  {r['title'][:30]}")


if __name__ == "__main__":
    main()
