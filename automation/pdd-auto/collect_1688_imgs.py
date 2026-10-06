#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 1688 直铺的货源补图（主图多张 + 详情图），供拼多多轮播与商详使用.

跑法: automation/venv/bin/python collect_1688_imgs.py [--limit N] [--ids a,b] [--test]
  前置: 9223 的 Chrome 起着且 **1688 登录态有效**（sourcing/chrome-profile-sourcing；
        登录态大概 2026-09-23 之后就过期了，跑之前先确认，过期要人工扫码）
  断点: pdd_imgs_progress.json 记已完成的 offerId

为什么需要一个新脚本: 现有 worklist 每条只有 1 张主图（采集时只留了 1 个 URL），
而拼多多轮播图与商详都吃这个 —— 单图商品在转化上吃亏。本地其它数据文件里也没有这批的图集
（sourcing_raw.jsonl 是另一批服装的搜索结果，且不含图），所以只能回 1688 详情页重取。

拆分原则：`normalize_url` / `pick_images` 是可测的纯函数，页面侧只负责"把看到的图 URL 塞进来"。
"""
import argparse
import asyncio
import json
import os
import random
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402

PROGRESS = os.path.join(C.BASE, "pdd_imgs_progress.json")
IMG_HOST = "cbu01.alicdn.com"
ICON_HINTS = ("logo", "icon", "sprite", "avatar", "qrcode", "placeholder")
RESIZE_MAX = 1080
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


_SUFFIX = re.compile(r"(_[0-9]+x[0-9]+)?(\.(?:jpg|jpeg|png|webp))$", re.I)


def normalize_url(u):
    """1688 CDN 同一张图带多种尺寸后缀，统一还原成原图。

    形态实测有三种：`abc.jpg`、`abc.jpg_310x310.jpg`、`abc.jpg_.webp`（还有 `abc_310x310.jpg`）。
    不归一的话同一张图会被当成 2~3 张分别下载，轮播里就是重复图。
    扩展名沿用基名自己的（.png 不会被改写成 .jpg，否则下载会 404）。
    """
    u = (u or "").split("?")[0]
    for _ in range(4):
        m = _SUFFIX.search(u)
        if not m:
            break
        base = u[:m.start()].rstrip("_")
        if re.search(r"\.(jpg|jpeg|png)$", base, re.I):
            u = base            # 基名已带扩展名（abc.jpg_310x310.jpg），继续剥外层
        else:
            u = base + m.group(2).lower()
            break
    return u


def pick_images(candidates, max_main=5, max_detail=8):
    """把页面上看到的图 URL 分成 (轮播主图, 详情图)。

    规则保守：只留 1688 图床、去掉图标/二维码、按出现顺序去重；
    前 max_main 张当轮播（详情页首屏那几张就是主图，顺序即优先级），其余当详情图。
    这个"前 N 张就是主图"的切分**尚未经真页面校准** —— 首跑要用 5 条验证：轮播图是否就是商品图，
    不对就调整切分（切分逻辑在这里，是纯函数，改完跑测试）。
    """
    out_main, out_detail, seen = [], [], set()
    for u in candidates:
        n = normalize_url(u)
        if not n or IMG_HOST not in n:
            continue
        if any(h in n.lower() for h in ICON_HINTS):
            continue
        if n in seen:
            continue
        seen.add(n)
        (out_main if len(out_main) < max_main else out_detail).append(n)
        if len(out_main) >= max_main and len(out_detail) >= max_detail:
            break
    return out_main, out_detail


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/jpeg,image/png",
                                               "Referer": "https://detail.1688.com/"})
    data = urllib.request.urlopen(req, timeout=30).read()
    with open(path, "wb") as f:
        f.write(data)
    subprocess.run(["sips", "-Z", str(RESIZE_MAX), path], capture_output=True)
    return len(data)


async def fetch_images(page, offer_id):
    """打开详情页，把响应体与 DOM 里出现的图 URL 全都收进来（不预设接口名）。"""
    seen = []

    async def on_resp(r):
        try:
            if any(k in r.url for k in ("1688.com", "alicdn.com")):
                body = await r.text()
                if IMG_HOST in body:
                    seen.extend(re.findall(r"https://" + IMG_HOST.replace(".", r"\.") + r"/[^\"'\\\s]+?\.(?:jpg|png)(?:_[0-9]+x[0-9]+\.jpg)?", body))
        except Exception:
            pass

    page.on("response", lambda r: asyncio.create_task(on_resp(r)))
    await page.goto(f"https://detail.1688.com/offer/{offer_id}.html",
                    wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(random.uniform(2.5, 4))
    try:
        dom = await page.evaluate(
            """()=>[...document.querySelectorAll('img')].map(i=>i.src||i.dataset.src||'').filter(Boolean)""")
        seen.extend(dom)
    except Exception:
        pass
    return seen


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--test", action="store_true", help="只取 URL 不下载图片")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(C.WORKLIST_1688, encoding="utf-8") if l.strip()]
    only = {x.strip() for x in args.ids.split(",") if x.strip()}
    if only:
        rows = [r for r in rows if r["item_id"] in only]
    if args.limit:
        rows = rows[: args.limit]

    prog = json.load(open(PROGRESS)) if os.path.exists(PROGRESS) else {"done": []}
    done = set(prog["done"])
    b, ctx = await connect_cdp(C.CDP_PORT_SOURCING, keep_urls=["1688.com"], log=print)
    page = await ctx.new_page()
    try:
        for n, rec in enumerate(rows, 1):
            oid = rec["item_id"]
            if oid in done and not only:
                continue
            print(f"[{n}/{len(rows)}] {oid}")
            cands = await fetch_images(page, oid)
            main, detail = pick_images(cands)
            print(f"  抓到 {len(cands)} 个 URL -> 主图 {len(main)} / 详情 {len(detail)}")
            if len(main) < 2:
                print("  ⚠ 主图不足 2 张，可能是登录态失效或页面结构变了，先人工确认再继续")
                break
            if args.test:
                print("   ", main[:3])
                continue
            d = os.path.join(C.IMG_ROOT_1688, oid)
            os.makedirs(d, exist_ok=True)
            for i, u in enumerate(main, 1):
                p = os.path.join(d, f"main_{i}.jpg")
                if not os.path.exists(p):
                    download(u, p)
            for i, u in enumerate(detail, 1):
                p = os.path.join(d, f"detail_{i}.jpg")
                if not os.path.exists(p):
                    download(u, p)
            prog["done"].append(oid)
            json.dump(prog, open(PROGRESS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
