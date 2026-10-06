#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 发布页探路: 只读 dump 页面结构(字段/必填/控件), 不点提交.
跑法: automation/venv/bin/python probe_pdd_publish.py
前置: run_chrome_pdd.sh 已起 9224 且已登录 mms.pinduoduo.com
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
import pdd_config as C  # noqa: E402


async def main():
    b, ctx = await connect_cdp(C.CDP_PORT, keep_urls=["pinduoduo.com"], log=print)
    page = await ctx.new_page()
    try:
        await page.goto(C.MMS_GOODS_PUBLISH, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(6)
        url = page.url
        title = await page.title()
        body = (await page.inner_text("body"))[:4000]
        dom = await page.evaluate(
            """() => {
              const pick = (sel) => [...document.querySelectorAll(sel)].map(e => ({
                tag: e.tagName, id: e.id || '', name: e.name || '',
                text: (e.innerText || e.placeholder || e.getAttribute('aria-label') || '')
                        .replace(/\\s+/g, ' ').trim().slice(0, 60)
              })).filter(x => x.text);
              return {buttons: pick('button'), inputs: pick('input'),
                      selects: pick('select'), labels: pick('label'),
                      textareas: pick('textarea')};
            }"""
        )
        os.makedirs(C.NOTES, exist_ok=True)
        out = os.path.join(C.NOTES, f"probe_publish_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"URL: {url}\nTITLE: {title}\n\n== BODY ==\n{body}\n\n== DOM ==\n{dom}\n")
        print("WROTE", out)
        print("URL:", url[:120])
        print("BODY(head):", body[:200].replace("\n", " "))
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass


asyncio.run(main())
