#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_traffic_dom.py — 摸流量解析页搜索框/查询按钮的选择器（只读现有标签，零导航零查询）。

背景：2026-10-17 用户指示不要整页刷新流量解析（易触发滑块），改为「替换搜索词→点查询」页内刷新。
本探针只 evaluate 现有标签的 DOM，找：可见文本输入框（含旧词/placeholder）、查询按钮。
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222

JS = r"""() => {
  const vis = e => !!(e.offsetWidth || e.offsetHeight);
  const inputs = [...document.querySelectorAll('input')].filter(vis).map(e => ({
    type: e.type || '(none)', cls: (e.className || '').slice(0, 140),
    placeholder: e.placeholder || '', value: (e.value || '').slice(0, 40),
    readOnly: e.readOnly, parentCls: ((e.closest('div') || {}).className || '').slice(0, 140),
  }));
  const btns = [];
  [...document.querySelectorAll('button, span, a, div')].forEach(e => {
    if (!vis(e) || e.children.length > 2) return;
    const t = (e.innerText || '').replace(/\s+/g, '').trim();
    if (t === '查询' || t === '搜索' || t === '确定') {
      btns.push({ tag: e.tagName, text: t, cls: (e.className || '').slice(0, 140),
                  parentCls: ((e.parentElement || {}).className || '').slice(0, 140) });
    }
  });
  const seen = new Set(); const ub = [];
  for (const b of btns) { const k = b.tag + b.text + b.cls; if (!seen.has(k)) { seen.add(k); ub.push(b); } }
  return { url: location.hash.slice(0, 90), inputs, btns: ub };
}"""


async def main():
    log = lambda m: print(m, flush=True)
    b, ctx = await connect_cdp(PORT, keep_urls=["alimama.com", "taobao.com"], log=log)
    target = None
    for p in ctx.pages:
        if "traffic-analysis" in p.url:
            target = p
            break
    if not target:
        log("没有已开的流量解析标签")
        return
    log(f"使用现有标签: {target.url[:110]}")
    data = await target.evaluate(JS)
    print(json.dumps(data, ensure_ascii=False, indent=1))


asyncio.run(main())
