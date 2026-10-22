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


async def minimize_windows(ctx, log=print):
    """把该 Chrome 实例的窗口最小化.

    两个已知弹窗来源的对策 (2026-10-16 实测):
      1. macOS 把 --window-position=-32000 的离屏窗口钳回可视区;
      2. 新开标签(ctx.new_page)会把最小化窗口顶回前台.
    CDP Browser.setWindowBounds 无辅助功能权限问题。headless 实例无窗口,
    CDP 调用异常逐页吞掉即可。
    """
    done = set()
    for page in list(ctx.pages):
        try:
            s = await ctx.new_cdp_session(page)
            info = await s.send("Browser.getWindowForTarget")
            wid = info.get("windowId")
            if not wid or wid in done:
                continue
            cur = (info.get("bounds") or {}).get("windowState")
            if cur != "minimized":
                await s.send("Browser.setWindowBounds",
                             {"windowId": wid, "bounds": {"windowState": "minimized"}})
            done.add(wid)
        except Exception:
            continue
    if done:
        log(f"[cdp_utils] 窗口已最小化: {sorted(done)}")
    return sorted(done)


async def connect_cdp(port: int, keep_urls=None, log=print, minimize=False):
    """连接指定端口的 CDP Chrome, 启动时清理孤儿标签页.

    minimize=True: 连接后把窗口压回最小化 (9222 窗口模式防打扰; 用户要看窗口
    / 要人工拖滑块的场景别开, 会把验证码藏起来)。
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
    if minimize:
        try:
            await minimize_windows(ctx, log)
        except Exception:
            pass
    return b, ctx


async def new_page_quiet(ctx, url=None, wait_until="domcontentloaded", timeout=40000, log=print):
    """新开标签并立刻把窗口压回最小化 (新标签激活会把最小化窗口顶回前台).

    同站多次导航尽量复用已有标签 (跨域 goto 是整页重载, 无 SPA 缓存问题);
    确需新标签时一律用本函数代替裸 ctx.new_page().
    """
    p = await ctx.new_page()
    if url:
        await p.goto(url, wait_until=wait_until, timeout=timeout)
    try:
        await minimize_windows(ctx, log)
    except Exception:
        pass
    return p


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
