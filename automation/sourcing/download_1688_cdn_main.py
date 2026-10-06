#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从已采集的 worklist jsonl 里取 1688 主图 CDN 原链, 直连下载(不受详情页 IP 限流影响),
按 换图清单.csv 落到 /Users/qyk9527/tb/<itemId>/ 并打包 `1688_<offerId> <标题>.zip`。

主图链存在 douyin_worklist.jsonl / guiruo_dropship_worklist.jsonl 的 img_uris
(相对路径 `img/ibank/xxx_!!seller-0-cib[.310x310].jpg`)。去掉 `.NxN` 后缀即原图(实测 800~1409px)。
与 download_1688_materials.py 共用进度 tb_1688_img_download_progress.json(done/gone/failed),
跑完的 itemId 会被详情页循环自动跳过。

跑法: automation/venv/bin/python download_1688_cdn_main.py [--limit N] [--ids a,b] [--test]
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from download_1688_materials import clean_title, img_size, load_progress, save_progress  # noqa: E402

CSV_FILE = "/Users/qyk9527/tb/换图清单.csv"
OUT_ROOT = "/Users/qyk9527/tb"
SOURCES = ["douyin_worklist.jsonl", "guiruo_dropship_worklist.jsonl"]
HOST = "https://cbu01.alicdn.com/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0 Safari/537.36")
MIN_SIDE = 500
_SIZE = re.compile(r"\.\d+x\d+(\.(?:jpg|jpeg|png|webp))$", re.I)


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def full_url(u):
    if not u:
        return ""
    if not u.startswith("http"):
        u = HOST + u.lstrip("/")
    return _SIZE.sub(lambda m: m.group(1), u)


def build_pool():
    pool = {}
    for fn in SOURCES:
        p = os.path.join(BASE, fn)
        if not os.path.exists(p):
            log(f"缺 {fn}, 跳过")
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                oid = str(d.get("offerId") or "")
                us = [full_url(x) for x in (d.get("img_uris") or [])]
                us = [x for x in us if x]
                if oid and us:
                    pool.setdefault(oid, [])
                    for x in us:
                        if x not in pool[oid]:
                            pool[oid].append(x)
    return pool


def load_rows():
    rows = []
    with open(CSV_FILE, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("offerId"):
                rows.append(r)
    return rows


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://detail.1688.com/"})
    data = urllib.request.urlopen(req, timeout=40).read()
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    pool = build_pool()
    rows = load_rows()
    only = {x.strip() for x in args.ids.split(",") if x.strip()}
    prog = load_progress()
    done, gone = set(prog["done"]), set(prog["gone"])

    todo = []
    for r in rows:
        iid, off = r["itemId"], str(r["offerId"])
        if iid in done or iid in gone:
            continue
        if only and iid not in only:
            continue
        if off in pool:
            todo.append((r, pool[off]))
    if args.limit:
        todo = todo[: args.limit]

    log(f"清单 {len(rows)}, CDN 可覆盖 {sum(1 for r in rows if str(r['offerId']) in pool)}, 本次 {len(todo)}")
    ok = fail = 0
    for n, (r, urls) in enumerate(todo, 1):
        iid, off = r["itemId"], str(r["offerId"])
        outdir = os.path.join(OUT_ROOT, iid)
        log(f"[{n}/{len(todo)}] {iid} <- offer {off} ({len(urls)} 图) ...")
        try:
            if args.test:
                continue
            os.makedirs(outdir, exist_ok=True)
            files = []
            for i, u in enumerate(urls, 1):
                p = os.path.join(outdir, f"main_{i}.jpg")
                download(u, p)
                w, h = img_size(p)
                if w < MIN_SIDE:
                    os.remove(p)
                    continue
                files.append(p)
            if not files:
                raise RuntimeError("无有效主图(像素过小)")
            zname = f"1688_{off} {clean_title(r.get('title',''))}.zip"
            with zipfile.ZipFile(os.path.join(outdir, zname), "w", zipfile.ZIP_DEFLATED) as z:
                for p in files:
                    z.write(p, os.path.basename(p))
            for p in files:
                try:
                    os.remove(p)
                except Exception:
                    pass
            done.add(iid)
            prog["done"] = sorted(done)
            prog["failed"].pop(iid, None)
            save_progress(prog)
            ok += 1
            log(f"  ✓ {zname} (主图{len(files)})")
        except Exception as e:
            fail += 1
            msg = str(e)[:120]
            prog["failed"][iid] = {"offerId": off, "error": msg}
            save_progress(prog)
            log(f"  ✗ {msg}")
        time.sleep(0.2)
    log(f"完成: 成功 {ok} 失败 {fail}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("手动中断")
