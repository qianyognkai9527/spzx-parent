"""把 sourcing 采集的优质商品+厂家落库到 spzx 的 db_spzx。
- source_factory:按 company(厂名)去重聚合,存工厂排行榜
- source_product:按 offerId(source_product_code)去重,关联 source_factory_id
用法: python import_to_db.py
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime
import pymysql
from source_config import MIN_TRUST_YEARS
from grade_quality import grade_product, grade_factory

RAW_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/sourcing_raw.jsonl"
DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}


def parse_sales(s):
    m = re.match(r"(\d+)", s or "")
    return int(m.group(1)) if m else 0


def parse_rep(s):
    m = re.match(r"(\d+)", s or "")
    return int(m.group(1)) if m else 0


def parse_price(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_raw():
    rows = []
    if not os.path.exists(RAW_FILE):
        print(f"找不到 {RAW_FILE}")
        return rows
    with open(RAW_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def main():
    rows = load_raw()
    print(f"原始数据 {len(rows)} 条")

    # 硬筛:诚信通>=3 (命中优质标识 五星供应链/超级工厂/全球供 的厂家不受年限限制)
    rows_kept = []
    for r in rows:
        if (r.get("trustYears") or 0) >= MIN_TRUST_YEARS:
            rows_kept.append(r)
        elif r.get("supply_badge"):
            rows_kept.append(r)
    rows = rows_kept
    print(f"硬筛 诚信通>={MIN_TRUST_YEARS}年(或优质标识) 后 {len(rows)} 条")

    # 聚合厂家
    fac_agg = defaultdict(lambda: {"trust_years": 0, "count": 0, "rep_sum": 0, "rep_n": 0,
                                    "sales_sum": 0, "categories": defaultdict(int),
                                    "rep_offer": "", "rep_url": "", "badge": ""})
    for r in rows:
        name = (r.get("company") or "").strip() or "(未知供应商)"
        d = fac_agg[name]
        d["trust_years"] = max(d["trust_years"], r.get("trustYears") or 0)
        d["count"] += 1
        rep = parse_rep(r.get("repurchase"))
        if rep:
            d["rep_sum"] += rep
            d["rep_n"] += 1
        d["sales_sum"] += parse_sales(r.get("sales"))
        cat = r.get("category") or ""
        if cat:
            d["categories"][cat] += 1
        if not d["rep_offer"] and r.get("offerId"):
            d["rep_offer"] = r["offerId"]
            d["rep_url"] = r.get("detailUrl", "")
        # 优质标识: 五星供应链>超级工厂>全球供, 取最高
        badge = r.get("supply_badge") or ""
        if badge:
            rank = {"五星供应链": 3, "超级工厂": 2, "全球供": 1}
            cur = rank.get(d["badge"], 0)
            if rank.get(badge, 0) > cur:
                d["badge"] = badge
    print(f"聚合厂家 {len(fac_agg)} 家")

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 入库 source_factory(按 factory_name 去重:存在则更新,不存在则插入)
    fac_id_map = {}  # 厂名 -> source_factory.id
    fac_inserted = 0
    fac_updated = 0
    for name, d in fac_agg.items():
        avg_rep = round(d["rep_sum"] / d["rep_n"], 1) if d["rep_n"] else None
        main_cat = max(d["categories"], key=d["categories"].get) if d["categories"] else None
        grade = grade_factory(d["trust_years"], avg_rep, d["sales_sum"], d["count"])
        # 优质标识提升等级: 五星供应链->SS, 超级工厂/全球供->S (均高于A)
        badge = d.get("badge") or ""
        if badge == "五星供应链":
            if grade not in ("SSS", "SS"):
                grade = "SS"
        elif badge:
            if grade not in ("SSS", "SS", "S"):
                grade = "S"
        cur.execute("SELECT id FROM source_factory WHERE factory_name=%s AND platform_type=1 AND is_deleted=0", (name,))
        existing = cur.fetchone()
        if existing:
            fid = existing[0]
            cur.execute("""UPDATE source_factory SET trust_years=%s, product_count=%s, avg_repurchase_rate=%s,
                           total_sales=%s, category_name=%s, rep_offer_id=%s, rep_product_url=%s, quality_grade=%s,
                           update_time=%s WHERE id=%s""",
                         (d["trust_years"], d["count"], avg_rep, d["sales_sum"], main_cat,
                          d["rep_offer"], d["rep_url"], grade, now, fid))
            fac_updated += 1
        else:
            cur.execute("""INSERT INTO source_factory
                           (factory_name, trust_years, product_count, avg_repurchase_rate, total_sales,
                            category_name, rep_offer_id, rep_product_url, platform_type, quality_grade,
                            create_time, is_deleted)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,0)""",
                         (name, d["trust_years"], d["count"], avg_rep, d["sales_sum"],
                          main_cat, d["rep_offer"], d["rep_url"], grade, now))
            fid = cur.lastrowid
            fac_inserted += 1
        fac_id_map[name] = fid
    conn.commit()
    print(f"source_factory: 新增 {fac_inserted} 家, 更新 {fac_updated} 家")

    # 2. 入库 source_product(按 source_product_code=offerId 去重)
    # 新商品仅入库优质(C+); 已存在商品刷新统计+重算等级(可升降级)
    prod_inserted = 0
    prod_updated = 0
    prod_skipped = 0
    for r in rows:
        offer_id = r.get("offerId") or ""
        if not offer_id:
            continue
        company = (r.get("company") or "").strip()
        sid = fac_id_map.get(company)
        price = parse_price(r.get("price"))
        rep = parse_rep(r.get("repurchase"))
        sales = parse_sales(r.get("sales"))
        trust = r.get("trustYears") or 0
        title = (r.get("title") or "")[:200]
        grade = grade_product(trust, rep, sales)
        cur.execute("SELECT id FROM source_product WHERE source_product_code=%s AND is_deleted=0", (offer_id,))
        existing = cur.fetchone()
        if existing:
            cur.execute("""UPDATE source_product SET source_product_name=%s, source_product_url=%s, source_price=%s,
                           supplier_name=%s, repurchase_rate=%s, sales_count=%s, category_name=%s, keyword=%s,
                           trust_years=%s, source_factory_id=%s, data_source=1, quality_grade=%s,
                           head_img_url=%s, crawl_time=%s, update_time=%s WHERE id=%s""",
                         (title, r.get("detailUrl"), price, company, rep, sales,
                          r.get("category"), r.get("keyword"), trust, sid, grade,
                           r.get("headImgUrl") or r.get("head_img_url"), now, now, existing[0]))
            prod_updated += 1
        elif grade is not None:
            cur.execute("""INSERT INTO source_product
                           (source_product_name, source_product_code, source_product_url, source_price,
                            steady_status, eval_with_image_count, supplier_name, repurchase_rate, sales_count,
                            category_name, keyword, trust_years, source_factory_id, crawl_time,
                            platform_type, data_source, quality_grade, head_img_url, create_time, is_deleted)
                           VALUES (%s,%s,%s,%s,1,0,%s,%s,%s,%s,%s,%s,%s,%s,1,1,%s,%s,%s,0)""",
                         (title, offer_id, r.get("detailUrl"), price,
                          company, rep, sales, r.get("category"), r.get("keyword"),
                           trust, sid, now, grade, r.get("headImgUrl") or r.get("head_img_url"), now))
            prod_inserted += 1
        else:
            prod_skipped += 1
    conn.commit()
    print(f"source_product: 新增 {prod_inserted} 条, 更新 {prod_updated} 条, 跳过非优质 {prod_skipped} 条")

    cur.close()
    conn.close()
    print("\n🎉 落库完成!")


if __name__ == "__main__":
    main()
