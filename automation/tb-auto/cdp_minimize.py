#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cdp_minimize.py — 用 CDP 把指定端口的 Chrome 窗口最小化（不需要辅助功能权限）。

背景：macOS 会把"完全离屏"的窗口钳回可视区(--window-position=-32000 实测失效)，而
launchd 里 osascript 无辅助功能权限。CDP 的 Browser.setWindowBounds 无此限制。

用法: automation/venv/bin/python cdp_minimize.py [port]   # 默认 9222
"""
import sys

from playwright.sync_api import sync_playwright


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9222
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        done = set()
        for ctx in b.contexts:
            for page in ctx.pages:
                try:
                    s = ctx.new_cdp_session(page)
                    info = s.send("Browser.getWindowForTarget")
                    wid = info.get("windowId")
                    if wid in done:
                        continue
                    cur = (info.get("bounds") or {}).get("windowState")
                    if cur != "minimized":
                        s.send("Browser.setWindowBounds",
                               {"windowId": wid, "bounds": {"windowState": "minimized"}})
                    done.add(wid)
                except Exception:
                    continue
        b.close()
    print(f"minimized: {sorted(done)}" if done else "no windows")


if __name__ == "__main__":
    main()
