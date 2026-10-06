#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 /Users/qyk9527/tb/换图清单.csv 逐个 1688 货源页抓「主图 + 详情图(+视频)」,
下载到 /Users/qyk9527/tb/<itemId>/ 并打包成 `1688_<offerId> <1688标题>.zip`.

背景: 盗图(PIC_STEAL)商品需换自有图。系统 Chrome 154 已禁用命令行加载扩展, 官方
「1688采购助手」只能靠 Playwright+Chrome for Testing 驱动, 且其下载需登录、按钮是
混淆 React 点不稳 —— 故改为脚本复刻: 详情页**免登录即渲染**。
  · 主图: #gallery 图集(实测 800x800 原图, 最干净, 就是换盗图要用的)
  · 详情图: 详情区不在主文档, 只能从网络响应里捞图 URL; 下载后按像素宽度过滤掉缩略图(<MIN_SIDE)

跑法: automation/venv/bin/python download_1688_materials.py [--limit N] [--ids a,b] [--test] [--retry-failed]
  --test 只统计不下载
进度: tb_1688_img_download_progress.json {done, gone, failed}
"""
import argparse
import asyncio
import csv
import json
import os
import random
import re
import struct
import sys
import time
import urllib.request
import zipfile

from playwright.async_api import async_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = "/Users/qyk9527/tb/换图清单.csv"
OUT_ROOT = "/Users/qyk9527/tb"
PROGRESS = os.path.join(BASE, "tb_1688_img_download_progress.json")
CFT = ("/Users/qyk9527/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/"
       "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
TMP = "/var/folders/fy/994bdy0d7v786h09vnhqhht40000gn/T/opencode"
IMG_HOST = "cbu01.alicdn.com"
# 详情页免登录即渲染; 用过的固定 profile 一旦被 1688 打标会持续返回验证码(实测连吃 3 轮/70min),
# 故每轮运行启一个全新 profile, 从根上绕开被锁会话。可用 --profile 复用以调试。
GONE_HINTS = ("商品已下架", "宝贝已下架", "该商品已下架", "商品不存在",
              "页面不存在", "此商品已删除", "无法查看该商品")
BLOCK_HINTS = ("验证码", "请按照说明", "拖动滑块", "密码登录", "登录页面", "亲，请登录")
VIDEO_RE = re.compile(r"https?://[^\"'\\\s]+?\.(?:mp4|mov)", re.I)
ICON_HINTS = ("logo", "icon", "sprite", "avatar", "qrcode", "placeholder", "blank", "default")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0 Safari/537.36"
MIN_SIDE = 500          # 详情图最小边(像素), 低于视为缩略图丢弃
MAX_DETAIL = 40

_SUFFIX = re.compile(r"(_[0-9]+x[0-9]+)?(\.(?:jpg|jpeg|png|webp))$", re.I)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def normalize_url(u):
    """1688 CDN 同一张图带多种尺寸后缀, 还原成原图; 扩展名沿用基名(避免 png 被改 jpg 后 404)。"""
    u = (u or "").split("?")[0]
    for _ in range(4):
        m = _SUFFIX.search(u)
        if not m:
            break
        base = u[:m.start()].rstrip("_")
        if re.search(r"\.(jpg|jpeg|png)$", base, re.I):
            u = base
        else:
            u = base + m.group(2).lower()
            break
    return u


def unique_imgs(cands, max_n):
    out, seen = [], set()
    for u in cands:
        n = normalize_url(u)
        if not n or IMG_HOST not in n:
            continue
        if any(h in n.lower() for h in ICON_HINTS):
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
        if len(out) >= max_n:
            break
    return out


def img_size(path):
    """读图片像素宽高(纯 python, 无 PIL)。返回 (w,h), 失败 (0,0)。"""
    try:
        with open(path, "rb") as f:
            head = f.read(2)
            if head == b"\xff\xd8":                       # JPEG
                f.seek(0)
                data = f.read(4096)
                i = 2
                while i < len(data) - 9:
                    if data[i] != 0xFF:
                        i += 1
                        continue
                    marker = data[i + 1]
                    if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        h, w = struct.unpack(">HH", data[i + 5:i + 9])
                        return w, h
                    if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                        i += 2
                    else:
                        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                        i += 2 + seg
                return 0, 0
            if head == b"\x89P":                          # PNG
                data = open(path, "rb").read(33)
                w, h = struct.unpack(">II", data[16:24])
                return w, h
    except Exception:
        pass
    return 0, 0


def load_rows():
    rows = []
    with open(CSV_FILE, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("offerId"):
                rows.append(r)
    return rows


def load_progress():
    if os.path.exists(PROGRESS):
        try:
            d = json.load(open(PROGRESS, encoding="utf-8"))
            d.setdefault("done", [])
            d.setdefault("gone", [])
            d.setdefault("failed", {})
            return d
        except Exception:
            pass
    return {"done": [], "gone": [], "failed": {}}


def save_progress(p):
    tmp = PROGRESS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PROGRESS)


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://detail.1688.com/"})
    data = urllib.request.urlopen(req, timeout=40).read()
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def clean_title(t):
    t = (t or "").strip()
    for suf in ("-阿里巴巴", "-1688.com", "- 阿里巴巴"):
        if t.endswith(suf):
            t = t[: -len(suf)].strip()
    return re.sub(r"[\\/:*?\"<>|\n\r\t]", " ", t).strip()


async def grab(page, offer):
    """返回 dict: {status: ok|blocked|gone, main, cand, vids, title, head}。
    先做「风控/下架」早判(不滚动, 省 ~10s), 仅正常页才滚动懒加载取图。"""
    resp_imgs, vids = [], []

    async def on_resp(r):
        try:
            u = r.url
            m = VIDEO_RE.search(u)
            if m:
                vids.append(m.group(0))
            if IMG_HOST in u and re.search(r"\.(jpg|jpeg|png)", u, re.I):
                resp_imgs.append(u)
                return
            if any(k in u for k in ("1688.com", "alicdn.com")):
                b = await r.text()
                if IMG_HOST in b:
                    resp_imgs.extend(re.findall(
                        r"https://" + IMG_HOST.replace(".", r"\.") + r"/[^\"'\\\s]+?\.(?:jpg|jpeg|png)", b))
        except Exception:
            pass

    handler = lambda r: asyncio.create_task(on_resp(r))   # noqa: E731
    page.on("response", handler)
    try:
        await page.goto(f"https://detail.1688.com/offer/{offer}.html",
                        wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.uniform(1.3, 2.2))
        title = await page.title()
        head = await page.evaluate("()=>(document.body.innerText||'').slice(0,140)")
        if any(h in title for h in ("验证码", "登录")) or any(h in head for h in BLOCK_HINTS):
            return {"status": "blocked", "title": title, "head": head}
        if any(h in head for h in GONE_HINTS) or ("已下架" in head and "查看" in head):
            return {"status": "gone", "title": title, "head": head}
        main = await page.evaluate(
            "()=>[...document.querySelectorAll('#gallery img, .od-gallery-list-wapper img')]"
            ".map(i=>i.src||i.dataset.src||'').filter(Boolean)")
        for _ in range(10):   # 滚动触发懒加载
            await page.mouse.wheel(0, 2600)
            await asyncio.sleep(random.uniform(0.5, 0.9))
        dom = await page.evaluate(
            "()=>[...document.querySelectorAll('img')].map(i=>i.src||i.dataset.src||i.dataset.lazySrc||'').filter(Boolean)")
        vids.extend(await page.evaluate(
            "()=>[...document.querySelectorAll('video,source')].map(v=>v.src||v.getAttribute('src')||'').filter(Boolean)"))
        head2 = await page.evaluate("()=>(document.body.innerText||'').slice(0,140)")
        if any(h in head2 for h in GONE_HINTS) or ("已下架" in head2 and "查看" in head2):
            return {"status": "gone", "title": title, "head": head2}
        main_set = set(normalize_url(u) for u in main)
        cand = list(resp_imgs) + [u for u in dom if normalize_url(u) not in main_set]
        return {"status": "ok", "main": main, "cand": cand, "vids": vids,
                "title": title, "head": head2}
    finally:
        page.remove_listener("response", handler)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--profile", default="")
    args = ap.parse_args()

    profile = args.profile or os.path.join(
        TMP, f"cft_1688_dl_{os.getpid()}_{int(time.time())}")

    rows = load_rows()
    only = {x.strip() for x in args.ids.split(",") if x.strip()}
    prog = load_progress()
    done, gone = set(prog["done"]), set(prog["gone"])
    failed = set(prog["failed"].keys())

    todo = []
    for r in rows:
        iid = r["itemId"]
        if iid in done or iid in gone:
            continue
        if iid in failed and not args.retry_failed:
            continue
        if only and iid not in only:
            continue
        todo.append(r)
    if args.limit:
        todo = todo[: args.limit]

    log(f"清单 {len(rows)} 个, 已完成 {len(done)}, gone {len(gone)}, failed {len(failed)}, 本次 {len(todo)}")
    log(f"profile: {profile}")

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            profile, executable_path=CFT, headless=False,
            args=["--window-position=-32000,-32000", "--disable-features=TranslateUI,site-per-process"],
            viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        ok_c = fail_c = gone_c = 0
        for n, r in enumerate(todo, 1):
            iid, offer = r["itemId"], r["offerId"]
            outdir = os.path.join(OUT_ROOT, iid)
            log(f"[{n}/{len(todo)}] {iid} <- offer {offer} ...")
            try:
                res = await grab(page, offer)
                if res["status"] == "blocked":
                    log("  ⚠ 1688 风控(验证码/登录页), 存进度并退出待冷却(exit 42)")
                    save_progress(prog)
                    await ctx.close()
                    sys.exit(42)
                if res["status"] == "gone":
                    gone.add(iid); gone_c += 1
                    prog["gone"] = sorted(gone); save_progress(prog)
                    log("  ⚠ 商品已下架, 标记 gone 跳过")
                    continue
                main = unique_imgs(res["main"], 20)
                cand = unique_imgs(res["cand"], 120)
                vids = sorted(set(res["vids"]))
                title = res["title"]
                log(f"  主图 {len(main)} / 详情候选 {len(cand)} / 视频 {len(vids)}")
                if len(main) < 2:
                    raise RuntimeError(f"主图不足({len(main)}), 可能风控或结构变化")
                if args.test:
                    continue
                os.makedirs(outdir, exist_ok=True)
                files = []
                for i, u in enumerate(main, 1):
                    p = os.path.join(outdir, f"main_{i}.jpg")
                    if not os.path.exists(p):
                        download(u, p)
                    files.append(p)
                di = 0
                for u in cand:
                    p = os.path.join(outdir, f"_cand_{di}.jpg")
                    try:
                        if not os.path.exists(p):
                            download(u, p)
                        w, _h = img_size(p)
                        if w >= MIN_SIDE:
                            di += 1
                            dp = os.path.join(outdir, f"detail_{di}.jpg")
                            os.replace(p, dp)
                            files.append(dp)
                        else:
                            os.remove(p)
                    except Exception:
                        if os.path.exists(p):
                            os.remove(p)
                    if di >= MAX_DETAIL:
                        break
                for i, u in enumerate(vids, 1):
                    ext = ".mp4" if u.lower().endswith(".mp4") else ".mov"
                    p = os.path.join(outdir, f"video_{i}{ext}")
                    try:
                        if not os.path.exists(p):
                            download(u, p)
                        files.append(p)
                    except Exception:
                        pass
                zname = f"1688_{offer} {clean_title(title)}.zip"
                with zipfile.ZipFile(os.path.join(outdir, zname), "w", zipfile.ZIP_DEFLATED) as z:
                    for p in files:
                        z.write(p, os.path.basename(p))
                for p in files:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
                done.add(iid); prog["done"] = sorted(done)
                prog["failed"].pop(iid, None)
                save_progress(prog)
                ok_c += 1
                log(f"  ✓ {zname} (主图{len(main)}+详情{di}+视频{len(vids)})")
            except Exception as e:
                fail_c += 1
                msg = str(e)[:120]
                prog["failed"][iid] = {"offerId": offer, "error": msg}
                save_progress(prog)
                log(f"  ✗ {msg}")
            await asyncio.sleep(random.uniform(3, 6))
            if n % 25 == 0:
                rest = random.uniform(40, 90)
                log(f"  已处理 {n}, 休息 {int(rest)}s 防风控...")
                await asyncio.sleep(rest)
        log(f"完成: 成功 {ok_c} 失败 {fail_c} gone {gone_c}")
        await ctx.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("手动中断")
