#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""千牛批量采集: 指定(或从 ISV 映射取)淘宝 itemId -> 标题/主图/价/库存 -> taobao_product_data.jsonl.
可断点续跑: 已采集的跳过; 失败项记 collect_failed.json 也跳过(避免卡进度).
跑法:
  automation/venv/bin/python collect_qianniu.py --from-isv [--limit N]
  automation/venv/bin/python collect_qianniu.py --ids 123,456
前置: 9222 已登录淘宝/千牛.
"""
import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402

EDITOR = "https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}"
ISV_MAP = os.path.join(C.SOURCING, "isv_offer_taobao_map.jsonl")
FAILED = os.path.join(C.BASE, "collect_failed.json")

EXTRACT_JS = r"""() => {
  const val = (sel) => { const e = document.querySelector(sel + ' input'); return e ? e.value : null; };
  const imgs = (sel) => [...document.querySelectorAll(sel + ' img')]
      .map(i => i.src).filter(s => s && s.includes('imgextra') && !s.includes('-2-tps-'));
  return {
    title: val('#sell-field-title'),
    price: val('#sell-field-price'),
    quantity: val('#sell-field-quantity'),
    outerId: val('#sell-field-outerId'),
    mainImages: [...new Set(imgs('#sell-field-mainImagesGroup'))].slice(0, 10),
    descImages: [...new Set(imgs('#sell-field-desc'))].slice(0, 30),
  };
}"""


def _load_set(path):
    if os.path.exists(path):
        try:
            return set(json.load(open(path)))
        except Exception:
            return set()
    return set()


def load_done():
    done = set()
    if os.path.exists(C.TAOBAO_DATA):
        for l in open(C.TAOBAO_DATA, encoding="utf-8"):
            l = l.strip()
            if l:
                try:
                    done.add(str(json.loads(l)["item_id"]))
                except Exception:
                    pass
    return done


def load_ids(args):
    if args.ids:
        return [x.strip() for x in args.ids.split(",") if x.strip()]
    ids = []
    for l in open(ISV_MAP, encoding="utf-8"):
        l = l.strip()
        if l:
            ids.append(str(json.loads(l)["taobao_item_id"]))
    return ids


async def collect_one(page, item_id):
    await page.goto(EDITOR.format(id=item_id), wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(5)
    d = await page.evaluate(EXTRACT_JS)
    try:
        pmin = float(d["price"]) if d["price"] else None
    except ValueError:
        pmin = None
    return {
        "item_id": str(item_id), "title": d["title"] or "", "main_images": d["mainImages"],
        "detail_images": d["descImages"], "skus": [], "price_min": pmin, "price_max": pmin,
        "code": d["outerId"], "stock": d["quantity"],
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--from-isv", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    ids = load_ids(args)
    done = load_done()
    failed = _load_set(FAILED)
    todo = [i for i in ids if i not in done and i not in failed]
    if args.limit:
        todo = todo[: args.limit]
    print(f"总 {len(ids)}, 已采 {len(done)}, 失败 {len(failed)}, 本次 {len(todo)}", flush=True)
    if not todo:
        return
    b, ctx = await connect_cdp(9222, keep_urls=["myseller.taobao.com", "item.upload.taobao.com", "1688.com"], log=print)
    page = await ctx.new_page()
    out = open(C.TAOBAO_DATA, "a", encoding="utf-8")
    try:
        for n, i in enumerate(todo, 1):
            try:
                rec = await asyncio.wait_for(collect_one(page, i), timeout=90)
            except Exception as e:
                failed.add(i)
                json.dump(sorted(failed), open(FAILED, "w"))
                print(f"[{n}/{len(todo)}] {i} 失败: {str(e)[:50]}", flush=True)
                continue
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            print(f"[{n}/{len(todo)}] {i} {rec['title'][:24]} img={len(rec['main_images'])} ¥{rec['price_min']}", flush=True)
            await asyncio.sleep(1)
    finally:
        out.close()
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
