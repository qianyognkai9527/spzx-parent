#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存量商品合规体检（只读，不改任何商品）.

跑法: automation/venv/bin/python audit_pdd_catalog.py [--offline]
  读 pdd_store_snapshot.json（在售清单）+ pdd_rejections.json（驳回台账）+ 规则库，
  出一份 pdd_notes/catalog_audit_<日期>.md：标题命中清单、划线价依据、驳回台账现状。
  --offline 跳过数据库检查（拿不到成交数据时按"未确认"报告，不猜）。

为什么单独一个脚本而不是接进发布流程：存量 256 件已经卖出去了，闸门只能拦新的；
存量要不要动、怎么动（改标题/改参考价）是经营决定，所以这里只出证据。
"""
import argparse
import json
import os
import time

import pdd_config as C
import pdd_compliance as G

NOTES = os.path.join(C.BASE, "pdd_notes")


def summarize(on_sale, rules, brands, ref_factor, has_sales_data):
    """纯函数：把在售清单折成结论。has_sales_data 为 False 时才把参考价判成"无依据"，
    True（有可核实的成交记录）时不再一片红，None（查不到）时同样不作为依据但标注未确认。"""
    title_hits = []
    for r in on_sale:
        ok, reasons = G.gate(r.get("title") or "", rules, brands)
        if not ok:
            title_hits.append({"goods_id": str(r.get("goods_id")), "title": r.get("title"),
                               "reasons": reasons})
    priced = [r for r in on_sale if str(r.get("price") or "").strip() not in ("", "--")]
    return {
        "total": len(on_sale),
        "title_hits": title_hits,
        "ref_price": {"factor": ref_factor, "priced": len(priced),
                      "no_basis": len(priced) if has_sales_data is False else 0,
                      "sales_data": has_sales_data},
    }


def sales_evidence():
    """有没有可核实的成交记录。order_info 是 2023 演示数据，这里按"2024 年起有没有订单"判。"""
    try:
        import pymysql
        conn = pymysql.connect(host="127.0.0.1", user="root", password="root123456",
                               database="db_spzx", port=3306, charset="utf8mb4")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM order_info WHERE create_time >= '2024-01-01'")
                n = cur.fetchone()[0]
            return (n > 0), f"order_info 里 2024 年起的订单 {n} 条"
        finally:
            conn.close()
    except Exception as e:
        return None, f"查不到订单数据({type(e).__name__})，未确认"


def render(doc, on_sale, ledger_gap, rejections, candidates, meta):
    L = []
    L.append(f"# 拼多多在售商品合规体检 {meta['now']}")
    L.append("")
    L.append(f"数据源：{meta['snapshot']}（快照时间 {meta['scraped_at']}）｜规则库 {meta['rules_meta']}")
    L.append("")
    L.append(f"在售 **{doc['total']}** 条")
    L.append("")
    L.append(f"## 1. 标题合规命中 {len(doc['title_hits'])} 条")
    if doc["title_hits"]:
        for h in doc["title_hits"]:
            L.append(f"- `{h['goods_id']}` {'; '.join(h['reasons'])} — {h['title']}")
    else:
        L.append("无命中（品牌词/极限词/功效词/平台红线词全过）。")
    L.append("")
    rp = doc["ref_price"]
    L.append("## 2. 商品参考价（划线价）")
    L.append(f"- 生效系数 `REF_PRICE_FACTOR` = **{rp['factor']}**，有价格的 {rp['priced']} 条")
    L.append(f"- 成交数据：{'有' if rp['sales_data'] is True else '没有' if rp['sales_data'] is False else '未确认'}"
             f"（{meta['sales_note']}）")
    if rp["no_basis"]:
        L.append(f"- **{rp['no_basis']} 条**的参考价是按下单倍数生成的，没有任何成交记录支撑 —— "
                 f"按《明码标价和禁止价格欺诈规定》第十六/十七条属「无依据的被比较价格」口径。")
        L.append("- 收口方式：把 `pdd_config.REF_PRICE_FACTOR` 调到使参考价≈单买价+0.01（仍满足平台"
                 "「必须大于最大单买价」），代价是价签观感与转化 —— 属经营决定，改一个数即可。")
    else:
        L.append("- 未发现「参考价无依据」问题（或有成交记录可支撑）。")
    L.append("")
    L.append("## 3. 驳回台账")
    L.append(f"- 累计驳回 {len(rejections)} 条（页面「已驳回」Tab 是临时的，以本台账为准）")
    if candidates:
        L.append(f"- **待确认品牌词候选 {len(candidates)} 个**：{'、'.join(sorted(candidates))} —— "
                 f"确认后写进 `pdd_config.BRAND_WORDS`")
    else:
        L.append("- 没有新的品牌词候选")
    L.append("")
    L.append("## 4. 台账与店铺的差额")
    for line in ledger_gap:
        L.append(f"- {line}")
    L.append("")
    L.append("> 本报告只读：不改标题、不改价签、不下架。要不要动存量由人决定。")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="不查数据库")
    args = ap.parse_args()

    doc = json.load(open(C.SNAPSHOT, encoding="utf-8"))
    on_sale = doc.get("on_sale") or []
    rej = json.load(open(C.REJECTIONS, encoding="utf-8")).get("rejected") or []
    rules_doc = G.load_rules()
    brands = G.brands_for_publish(C.BRAND_WORDS, rej, on_sale)
    candidates = G.derived_brands(rej, on_sale, known=set(C.BRAND_WORDS))

    has_sales, sales_note = (None, "已跳过(--offline)") if args.offline else sales_evidence()
    doc_sum = summarize(on_sale, rules_doc["rules"], brands, C.REF_PRICE_FACTOR, has_sales)

    # 台账 vs 在售：只列差额，不判断谁对
    logged = {}
    if os.path.exists(C.PDD_PRODUCTS):
        for line in open(C.PDD_PRODUCTS, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                logged[str(r["pdd_goods_id"])] = r
    live = {str(r["goods_id"]) for r in on_sale}
    gap = [f"台账 {len(logged)} 条 / 在售 {len(live)} 条",
           f"台账有、店铺不在售 {len(set(logged) - live)} 条（驳回/下架/删除）",
           f"店铺在售、台账没有 {len(live - set(logged))} 条（人工建的或落盘失败）"]

    meta = {"now": time.strftime("%Y-%m-%d %H:%M:%S"),
            "snapshot": os.path.basename(C.SNAPSHOT),
            "scraped_at": doc.get("scraped_at"),
            "rules_meta": f"v{rules_doc['_meta']['skill_version']} / 同步于 {rules_doc['_meta']['synced_at']}",
            "sales_note": sales_note}
    os.makedirs(NOTES, exist_ok=True)
    out = os.path.join(NOTES, f"catalog_audit_{time.strftime('%Y%m%d_%H%M')}.md")
    open(out, "w", encoding="utf-8").write(render(doc_sum, on_sale, gap, rej, candidates, meta))
    print(f"在售 {doc_sum['total']} | 标题命中 {len(doc_sum['title_hits'])} | "
          f"参考价无依据 {doc_sum['ref_price']['no_basis']} | 待确认候选 {len(candidates)}")
    print(f"WROTE {out}")


if __name__ == "__main__":
    main()
