#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_login.py — 9222 登录态预检（spec 2026-10-19-schedule-optimization §4.4）

连 CDP 9222 打开 ISV 控制台，判是否被踢到登录墙。exit 0=登录态 OK / 1=登录墙 / 2=探测异常。
只开自己的标签、只关自己的标签（绝不 b.close()，沿用 detect_stock_night.py 模式）。
不自动重登录——登录墙=人工扫码，包装层 skip 并写显式告警。
"""
import asyncio
import sys

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')

CONSOLE_URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"


def is_login_wall(url, has_password_input):
    """登录墙判定（纯函数）：控制台 URL 被重定向到登录域，或页面上有可见密码输入框。"""
    if any(h in (url or "") for h in ("login.taobao.com", "login.1688.com", "member/login")):
        return True
    return bool(has_password_input)


async def run():
    from cdp_utils import connect_cdp, new_page_quiet
    b, ctx = await connect_cdp(
        9222,
        keep_urls=["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com",
                   "taobao.com", "1688.com"],
        log=lambda m: print(m, flush=True))
    page = await new_page_quiet(ctx)
    try:
        await page.goto(CONSOLE_URL, timeout=30000)
        await asyncio.sleep(6)
        url = page.url
        pw = await page.evaluate("""() => {
          const vis = (i) => { const r = i.getBoundingClientRect();
                               return r.width > 20 && r.height > 10; };
          for (const i of document.querySelectorAll('input[type=password]'))
            if (vis(i)) return true;
          for (const f of document.querySelectorAll('iframe')) {
            try { const d = f.contentDocument; if (!d) continue;
              for (const i of d.querySelectorAll('input[type=password]'))
                if (vis(i)) return true; } catch (e) {}
          }
          return false; }""")
        wall = is_login_wall(url, pw)
        print(f"CHECK {'LOGIN_WALL' if wall else 'OK'} url={url[:120]} pw={pw}")
        return 1 if wall else 0
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass


def main():
    try:
        sys.exit(asyncio.run(run()))
    except Exception as e:
        print(f"CHECK PROBE_ERROR {e!r}")
        sys.exit(2)


if __name__ == "__main__":
    main()
