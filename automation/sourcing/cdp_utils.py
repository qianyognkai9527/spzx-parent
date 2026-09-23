#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CDP 连接工具: 统一处理标签页泄漏问题 (2026-08-17)

背景: `connect_over_cdp` 下 `browser.close()` 只断开连接, **不关真实 Chrome 标签页**;
脚本被 kill -9/pkill 强杀时连 page.close() 都不执行 -> 每跑一次漏 1 个 tab,
多次累积成 20+ 标签, 每个抖店编辑页是重型 React SPA 吃 30-40% CPU, 叠加即飙到 200-300%.

根治方案:
  1. `connect_cdp(port, keep_urls=[])`: 连接时自动清理本实例上"非保留"的孤儿标签页
  2. 所有 CDP 脚本统一使用本模块, 不再各自裸连 CDP
  3. 脚本结尾用 `page.close()` (参考 fix_drafts_images.py 三路径全关范式)

keep_urls: 启动时要保留的页面 URL 子串 (如批处理脚本自己即将用列表页,
           或者同一 Chrome 上另一任务的关键页)。默认全清(纯脚本场景)。
"""
import asyncio
from playwright.async_api import async_playwright, Playwright


def _is_orphan(url: str, keep_urls) -> bool:
    """判断一个页面是否是可清理的孤儿页.
    空白页/出错页/已关闭页一律视为孤儿; URL 含任一 keep_urls 则保留."""
    if not url or url.startswith("about:") or url.startswith("chrome://") or url == "about:blank":
        return True
    if url.startswith("data:"):
        return True
    for keep in keep_urls:
        if keep and keep in url:
            return False
    return True


async def connect_cdp(port: int, keep_urls=None, log=print):
    """连接指定端口的 CDP Chrome, 启动时清理孤儿标签页.

    返回 (browser, context). 调用方用完必须显式 `page.close()`.
    """
    keep_urls = keep_urls or []
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx = b.contexts[0]

    closed = 0
    for pg in list(ctx.pages):
        try:
            if _is_orphan(pg.url, keep_urls):
                await pg.close()
                closed += 1
        except Exception:
            # 页面已关闭/损坏, 无需处理
            pass
    if closed:
        log(f"[cdp_utils] port {port}: 启动清理孤儿标签 {closed} 个, 剩余 {len(ctx.pages)} 个")
    return b, ctx


async def close_pages(ctx, urls_substr=()):
    """按 URL 子串关闭页面 (用于运行中清理残留). 返回关闭数."""
    closed = 0
    for pg in list(ctx.pages):
        try:
            u = pg.url
            if not urls_substr or any(s in u for s in urls_substr):
                await pg.close()
                closed += 1
        except Exception:
            pass
    return closed
