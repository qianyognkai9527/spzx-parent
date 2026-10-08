#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入 PDD 商品 + 1688 货源 + 商品级关联(幂等).
数据: pdd_products.jsonl (goods_id<->item_id) + 两选一货源来源:
      - 1688 直铺批次: item_id 本身就是 offerId, 进价在 pdd_worklist_1688.jsonl 的 cost
      - 淘宝源批次  : item_id 是淘宝 itemId, 货源要查 ../sourcing/isv_offer_taobao_map.jsonl
动作: 缺则建 source_product; upsert platform_product(platform_type=3, code=PDD goods_id); 绑定 product_bind_relation
在架闸门: 有 pdd_store_snapshot.json(sync_pdd_store.py 抓的在售清单)时, 不在清单里的 goods_id
          不当在售商品导入, 只在 remark 标注 —— 提交成功不等于审核通过, 5 条被驳回的不能当好商品进库。
跑法: automation/venv/bin/python import_pdd_products.py [--dry-run]
"""
import argparse
import json
import os
import re

import pymysql

import pdd_config as C

import os as _os, sys as _sys  # dbconf 在 automation/sourcing 下，跨目录脚本按既有约定把它加进搜索路径
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), _os.pardir, "sourcing"))
from dbconf import DB_CONFIG as DB
PDD_PLATFORM = 3
PDD_SHOP_ID = 3
SNAPSHOT = os.path.join(C.BASE, "pdd_store_snapshot.json")


def load_pdd():
    rows = []
    for l in open(C.PDD_PRODUCTS, encoding="utf-8"):
        l = l.strip()
        if l:
            rows.append(json.loads(l))
    return rows


def load_snapshot():
    """在售快照 -> {goods_id}; 没有快照返回 None(表示不做在架过滤)."""
    if not os.path.exists(SNAPSHOT):
        return None
    try:
        doc = json.load(open(SNAPSHOT, encoding="utf-8"))
    except Exception:
        return None
    return {str(r["goods_id"]) for r in doc.get("on_sale") or []}


def load_1688():
    """1688 直铺 worklist: item_id(=offerId) -> {cost, title}."""
    out = {}
    if not os.path.exists(C.WORKLIST_1688):
        return out
    for l in open(C.WORKLIST_1688, encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        out[str(r["item_id"])] = r
    return out


def load_isv():
    p = os.path.join(C.SOURCING, "isv_offer_taobao_map.jsonl")
    out = {}
    if not os.path.exists(p):
        return out
    for l in open(p, encoding="utf-8"):
        l = l.strip()
        if l:
            r = json.loads(l)
            out[str(r["taobao_item_id"])] = r
    return out


def parse_source(text):
    """从商品管理行文本取货源价/供应商."""
    price = None
    m = re.search(r"货号：.*?([\d.]+)元", text)
    if m:
        price = float(m.group(1))
    sup = None
    m2 = re.search(r"货号：【\d+】\s*([^\s]+)", text)
    if m2:
        sup = m2.group(1)
    # 货源名: 第二个「预览」到「ID：」之间
    name = None
    mm = re.findall(r"预览\s*(.+?)(?:淘分销\s*)?ID：(\d+)", text)
    for nm, oid in mm:
        name = nm.strip()
    return name, price, sup


def ensure_source(conn, offer_id, name, price, supplier):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_product WHERE source_product_code=%s AND is_deleted=0", (offer_id,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO source_product(source_product_name,source_product_code,source_price,supplier_name,"
            "platform_type,create_by,steady_status,is_deleted,data_source,create_time) "
            "VALUES(%s,%s,%s,%s,1,0,0,0,1,NOW())",
            (name or ("1688货源" + offer_id), offer_id, price or 0, supplier))
    return cur.lastrowid


def upsert_platform_product(conn, goods_id, title, price, remark=None):
    with conn.cursor() as cur:
        cur.execute("SELECT id, platform_type FROM platform_product WHERE code=%s", (goods_id,))
        row = cur.fetchone()
        if row:
            if row[1] != PDD_PLATFORM:
                # platform_product.code 是全局唯一索引。拼多多 goods_id 和淘宝 itemId 今天不撞
                # （2026-10-05 实测 224 条对 4,683 条，0 命中），但一旦哪天撞上，
                # 按 code 更新会把那件淘宝商品直接改成平台类型 3、店铺改成拼多多店 —— 静默毁数据。
                # 宁可停下来让人看，也不能猜。
                raise SystemExit(
                    f"!! goods_id {goods_id} 已被 platform_type={row[1]} 的商品 id={row[0]} 占用，"
                    f" 中止导入以免把别的平台商品改写成拼多多。")
            cur.execute("UPDATE platform_product SET title=%s,pricing=%s,platform_type=%s,shop_id=%s,"
                        "remark=IFNULL(%s, remark) WHERE id=%s",
                        (title, price, PDD_PLATFORM, PDD_SHOP_ID, remark, row[0]))
            return row[0]
        cur.execute(
            "INSERT INTO platform_product(code,title,platform_type,shop_id,pricing,remark,create_by,create_time) "
            "VALUES(%s,%s,%s,%s,%s,%s,0,NOW())",
            (goods_id, title, PDD_PLATFORM, PDD_SHOP_ID, price, remark))
    return cur.lastrowid


def mark_off_sale(conn, goods_id, note):
    """台账里有、店铺在售清单里没有: 只标注, 不新建 —— 它可能是被驳回的, 当在售商品进库就是撒谎."""
    with conn.cursor() as cur:
        cur.execute("SELECT id, platform_type FROM platform_product WHERE code=%s", (goods_id,))
        row = cur.fetchone()
        if not row or row[1] != PDD_PLATFORM:
            # 同 upsert：code 全局唯一，撞上别的平台时宁可什么都不写
            return False
        cur.execute("UPDATE platform_product SET remark=%s WHERE id=%s", (note, row[0]))
        return True


def bind(conn, product_id, source_id):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM product_bind_relation WHERE product_id=%s AND source_productId=%s AND is_deleted=0",
                    (product_id, source_id))
        if cur.fetchone():
            return
        cur.execute("INSERT INTO product_bind_relation(product_id,source_productId,create_by,create_time,is_deleted) "
                    "VALUES(%s,%s,0,NOW(),0)", (product_id, source_id))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    pdd = {str(r["item_id"]): r for r in load_pdd()}
    isv = load_isv()
    w1688 = load_1688()
    live = load_snapshot()
    if live is None:
        print("!! 没有 pdd_store_snapshot.json —— 不做在架过滤(先跑 sync_pdd_store.py 再导更准)")
    conn = pymysql.connect(**DB)
    try:
        n = off = nomap = 0
        for item_id, pr in pdd.items():
            goods = str(pr["pdd_goods_id"])
            if live is not None and goods not in live:
                if not args.dry_run:
                    mark_off_sale(conn, goods, "台账有记录但店铺不在售(驳回/下架), 未当在售商品导入")
                off += 1
                print(f"◇ {goods} 不在售, 只标注 (item {item_id}) {pr['title'][:30]}")
                continue
            src = w1688.get(item_id)
            if src:
                offer, sname, sprice, sup = item_id, src.get("title"), src.get("cost"), None
            else:
                m = isv.get(item_id)
                if not m or not m.get("offer_id"):
                    nomap += 1
                    print(f"⚠ {item_id}: 既不在 1688 worklist 也无 ISV 映射, 跳过")
                    continue
                offer = m["offer_id"]
                sname, sprice, sup = parse_source(m.get("title", ""))
            if not args.dry_run:
                sid = ensure_source(conn, offer, sname, sprice, sup)
                pid = upsert_platform_product(conn, goods, pr["title"], pr["price"])
                bind(conn, pid, sid)
            n += 1
            print(f"✓ {item_id} -> PDD {goods} <- 1688 {offer} ({sname} {sprice} {sup})")
        if not args.dry_run:
            conn.commit()
        print(f"完成 {n}/{len(pdd)} 条 | 不在售只标注 {off} | 无货源映射 {nomap} (dry-run={args.dry_run})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
