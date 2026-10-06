#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 sourcing/1688_meijia_worklist.jsonl 转成拼多多可发布的 pdd_worklist_1688.jsonl.

跑法: automation/venv/bin/python build_pdd_worklist_1688.py --limit 3
     automation/venv/bin/python build_pdd_worklist_1688.py --ids 943513480713,...

与淘宝源(build_pdd_worklist.py)的三点不同, 都是数据决定的:
1. 图源是 1688 CDN 的 `...-cib.310x310.jpg` 缩略, 去掉 `.310x310` 才拿得到原图
   (实测还原后 921x921, 满足拼多多「轮播图 >480px / 商详图宽 480-1200px」两头)。
2. source_price 是**进价**, 不能套淘宝零售价那条 ×1.3。实际用的是 `pdd_price_markup`（进价 ×5），
   不是 `pdd_price_cost` 那条成本倒推 —— 后者只有单测在用，线上 146 件全是 ×5 定的价
   （0.6% 服务费下毛利率恒为 79.4%，不是 pdd_config 里写的目标 40%）。
   要换成成本倒推得先确认 40% 这个目标本身是他定的，别悄悄把已上架商品的价格口径换掉。
3. worklist 每条只有 1 张主图(采集时没留多图), 所以规格预览图只能循环复用这一张。

产出字段与淘宝源保持一致(item_id/title/price/stock/images), create_pdd_product.py 不用改。
"""
import argparse
import json
import os
import subprocess
import urllib.request

import pdd_config as C
import pdd_compliance as G
from pdd_map import (
    fit_pdd_title,
    hit_brand,
    hit_offcategory,
    pdd_price_markup,
    strip_b2b,
)

RULES = G.load_rules()["rules"]
# 驳回台账派生的提名词在建队列时不参与（快照可能不存在），
# 闸门在 create_pdd_product 那侧还会再跑一次，那里带台账。
BRANDS = set(C.BRAND_WORDS)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
MAX_MAIN = 5
RESIZE_MAX = 1080
MIN_EDGE = 480          # 拼多多主图下限, 低于这个直接跳过该货源而不是硬传


def orig_url(u):
    """1688 CDN 缩略 → 原图: 去掉尺寸段 .310x310."""
    for suf in (".310x310.jpg", ".310x310.png", ".220x220.jpg", ".120x120.jpg"):
        if u.endswith(suf):
            return u[: -len(suf)] + suf[suf.rfind("."):]
    return u


def download(u, path):
    req = urllib.request.Request(u, headers={
        "User-Agent": UA, "Accept": "image/jpeg,image/png",
        "Referer": "https://detail.1688.com/"})
    data = urllib.request.urlopen(req, timeout=30).read()
    with open(path, "wb") as f:
        f.write(data)
    subprocess.run(["sips", "-Z", str(RESIZE_MAX), path], capture_output=True)
    return len(data)


def load_rows():
    rows = []
    with open(C.MEIJIA_WORKLIST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build(limit=0, only_ids=None, skip_brand=True):
    img_root = C.IMG_ROOT_1688
    os.makedirs(img_root, exist_ok=True)
    out, dropped = [], {"brand": 0, "offcat": 0, "no_img": 0, "small_img": 0, "bad_price": 0,
                 "dup": 0, "compliance": 0}
    seen = set()
    for r in load_rows():
        oid = str(r.get("offerId") or "")
        if not oid:
            continue
        if only_ids and oid not in only_ids:
            continue
        if oid in seen:
            dropped["dup"] += 1
            continue
        seen.add(oid)

        title = fit_pdd_title(strip_b2b(r.get("title")))
        off = hit_offcategory(r.get("title"))
        if off:
            print(f"  [skip 非穿戴本体 {','.join(off)}] {oid} {title[:28]}")
            dropped["offcat"] += 1
            continue
        # 合规闸门（品牌词 + 广告法极限词/功效词）：在生成队列这一步就拦，
        # 别等到发布机上才发现 —— 那时每条都值一次驳回。
        ok, why = G.gate(title, RULES, BRANDS)
        if not ok:
            print(f"  [skip 合规 {','.join(why)}] {oid} {title[:30]}")
            dropped["compliance"] += 1
            continue
        brands = hit_brand(title)
        if brands:
            if skip_brand:
                print(f"  [skip 品牌词 {','.join(brands)}] {oid} {title[:30]}")
                dropped["brand"] += 1
                continue
            title = " ".join(w for w in title.split() if not any(b in w.lower() for b in brands))

        price = pdd_price_markup(r.get("source_price"))
        if not price:
            dropped["bad_price"] += 1
            continue

        uris = [orig_url(u) for u in (r.get("img_uris") or []) if u][:MAX_MAIN]
        if not uris:
            dropped["no_img"] += 1
            continue

        d = os.path.join(img_root, oid)
        os.makedirs(d, exist_ok=True)
        local = []
        for i, u in enumerate(uris, 1):
            p = os.path.join(d, f"main_{i}.jpg")
            if not os.path.exists(p) or os.path.getsize(p) == 0:
                try:
                    download(u, p)
                except Exception as e:
                    print(f"  [warn] {oid} img{i} 下载失败: {str(e)[:60]}")
                    continue
            w, h = png_size(p)
            if min(w, h) < MIN_EDGE:
                print(f"  [skip 主图过小 {w}x{h}] {oid}")
                dropped["small_img"] += 1
                local = []
                break
            local.append(p)
        if not local:
            continue

        out.append({
            "item_id": oid,
            "source": "1688",
            "title": title,
            "price": price,
            "stock": "",
            "images": local,
            "cost": r.get("source_price"),
        })
        print(f"{oid}: imgs={len(local)} 进价={r.get('source_price')} → 拼单价={price} {title[:26]}")
        if limit and len(out) >= limit:
            break

    with open(C.WORKLIST_1688, "w", encoding="utf-8") as f:
        for rec in out:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"WROTE {C.WORKLIST_1688} {len(out)} 条; 跳过 {dropped}")
    return out


def png_size(path):
    """用 sips 读宽高(venv 里的 PIL 是 x86_64, arm64 下 import 不了)."""
    try:
        r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                           capture_output=True, text=True, timeout=20).stdout
        vals = [int(line.split(":")[1]) for line in r.splitlines() if "pixel" in line]
        return (vals[0], vals[1]) if len(vals) >= 2 else (0, 0)
    except Exception:
        return (0, 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="", help="逗号分隔的 offerId, 只构建这些")
    ap.add_argument("--keep-brand", action="store_true", help="不跳过大牌词标题(不建议)")
    a = ap.parse_args()
    build(a.limit, {x.strip() for x in a.ids.split(",") if x.strip()}, not a.keep_brand)
