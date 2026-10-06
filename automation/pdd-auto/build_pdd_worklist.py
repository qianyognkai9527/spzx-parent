#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 taobao_product_data.jsonl 转成 pdd_worklist.jsonl: 还原原图+下载、标题清洗、价格×1.3.
跑法: automation/venv/bin/python build_pdd_worklist.py
图片落地 pdd_images/<item_id>/; 原图 URL 去掉 _320x320q80_.webp 缩略后缀,
下载必须带 Accept: image/jpeg(否则 CDN 返回 webp, PDD 只收 jpeg/png).
"""
import json
import os
import subprocess
import urllib.request

import pdd_config as C
from pdd_map import pdd_price, clean_pdd_title, hit_offcategory

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
MAX_MAIN = 5
# PDD 商详(图文详情)校验: 图片宽 480-1200px、高 ≤1500px; 轮播图要求 >480px.
# 原图常 ~1800px 超上限导致「商详装修校验」拦截提交, 故统一缩到 1080.
RESIZE_MAX = 1080


def orig_url(u):
    """去掉 alicdn 缩略后缀, 还原原图."""
    for suf in ("_320x320q80_.webp", "_400x400q90.jpg", "_q75.jpg"):
        if u.endswith(suf):
            return u[: -len(suf)]
    return u


def download(u, path):
    req = urllib.request.Request(u, headers={
        "User-Agent": UA, "Accept": "image/jpeg,image/png", "Referer": "https://item.taobao.com/"})
    data = urllib.request.urlopen(req, timeout=30).read()
    with open(path, "wb") as f:
        f.write(data)
    subprocess.run(["sips", "-Z", str(RESIZE_MAX), path], capture_output=True)  # 缩到 ≤1080px
    return len(data)


def build():
    img_root = os.path.join(C.BASE, "pdd_images")
    os.makedirs(img_root, exist_ok=True)
    out = []
    skipped = 0
    for line in open(C.TAOBAO_DATA, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        iid = r["item_id"]
        t = r.get("title") or ""
        # 只铺真穿戴甲: 标题须含"穿戴甲/甲片", 且不含配件/工具/脚甲/收纳等(错放类目)
        if ("穿戴甲" not in t and "甲片" not in t) or hit_offcategory(t):
            skipped += 1
            continue
        d = os.path.join(img_root, iid)
        os.makedirs(d, exist_ok=True)
        local = []
        for i, u in enumerate(r["main_images"][:MAX_MAIN], 1):
            p = os.path.join(d, f"main_{i}.jpg")
            if os.path.exists(p) and os.path.getsize(p) > 0:
                local.append(p)
                continue
            try:
                n = download(orig_url(u), p)
                local.append(p)
            except Exception as e:
                print(f"  [warn] {iid} img{i} 下载失败: {str(e)[:60]}")
        out.append({
            "item_id": iid,
            "title": clean_pdd_title(r["title"])[:60],
            "price": pdd_price(r["price_min"]),
            "stock": r.get("stock") or "",
            "images": local,
            "taobao_price": r["price_min"],
        })
        print(f"{iid}: imgs={len(local)} price={out[-1]['price']} title={out[-1]['title'][:26]}")
    with open(C.WORKLIST, "w", encoding="utf-8") as f:
        for rec in out:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("WROTE", C.WORKLIST, len(out), f"跳过非穿戴甲 {skipped}")


if __name__ == "__main__":
    build()
