#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1688 offer 详情页一次性采集（库存监控闭环共享模块，2026-10-18）。

一次导航同时拿：SKU API(canBookCount) + 页面正文(失效判定) + 标题/主图(建档用)。
detect_stock_change.fetch_source_skus 只抓 SKU 判不了死活；collect_1688_full 有判定但不复用结构。
消费者：backfill_offer_archive.py（P1 建档）、detect_stock_change --tiered（P2 刷新）。
"""
import asyncio
import json

SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"
# 与 download_1688_materials.GONE_HINTS 同一词表（7 词）；collect_1688_full.py:90 的守卫：登录/风控页不算下架
GONE_HINTS = ("商品已下架", "宝贝已下架", "该商品已下架", "商品不存在", "页面不存在",
              "此商品已删除", "无法查看该商品")


def is_gone(text):
    if not text:
        return False
    if "登录" in text or "验证" in text:
        return False
    return any(h in text for h in GONE_HINTS)


def parse_skus(payload):
    """queryofferskuselectormodel 响应体 -> SKU 列表（detect_stock_change 同款字段）。"""
    try:
        data = json.loads(payload)
        info = data.get("data", {}).get("skuSelectorBizModel", {}).get("skuInfoMap", {})
    except Exception:
        return []
    out = []
    for key, sv in info.items():
        if not isinstance(sv, dict):
            continue
        try:
            out.append({
                "sku_key": key.replace("&gt;", ">"),
                "sku_id": str(sv.get("skuId", "")),
                "stock": int(sv.get("canBookCount", 0)),
                "price": float(sv.get("price", 0)),
                "spec_id": str(sv.get("specId", "")),
            })
        except (TypeError, ValueError):
            continue
    return out


def extract_meta(page_title, og_image):
    """页面 <title> -> 商品名（取分隔符前段，≤200 字）；og:image -> 主图。"""
    t = (page_title or "").strip()
    for sep in (" - 阿里巴巴", "-阿里巴巴", " - 1688.com", "-1688.com"):
        if sep in t:
            t = t.split(sep)[0]
            break
    return t[:200], (og_image or None)


async def fetch_offer(page, offer_id, settle=3.0):
    """开详情页一次，返回 {skus, gone, title, img}。调用方负责 wait_for 超时与异常。"""
    captured = {}

    async def on_resp(r):
        if SKU_API in r.url:
            try:
                captured["body"] = await r.text()
            except Exception:
                pass

    page.on("response", on_resp)
    try:
        await page.goto(f"https://detail.1688.com/offer/{offer_id}.html", wait_until="domcontentloaded")
        await asyncio.sleep(settle)
        body = await page.evaluate("()=>document.body?document.body.innerText:''")
        title = await page.title()
        img = await page.evaluate(
            "()=>{const m=document.querySelector('meta[property=\"og:image\"]');return m?m.content:null}")
        return {"skus": parse_skus(captured.get("body", "")), "gone": is_gone(body),
                **dict(zip(("title", "img"), extract_meta(title, img)))}
    finally:
        page.remove_listener("response", on_resp)
