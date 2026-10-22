#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""恢复 9222 登录态: 检测到掉登录时, 用 login_cookies_backup.json 把 cookie 注回(设未来过期→持久化)。

为什么需要: 淘宝卖家登录的 cookie2/unb/_tb_token_/_l_g_ 是**会话级**(Chrome 重启即丢)。
只在“确认掉登录”时注入 —— 若登录仍有效就注入旧值会覆盖已刷新的 cookie2, 反而弄坏会话。
跑法: automation/venv/bin/python tb-auto/restore_login_cookies.py
返回码: 0=已登录(含注入成功) / 3=注入后仍登录失败(需人工扫码) / 2=无备份文件
"""
import asyncio
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from cdp_utils import connect_cdp  # noqa: E402

PORT = 9222
BACKUP = os.path.join(BASE, "login_cookies_backup.json")
CHECK_URL = "https://myseller.taobao.com/home.htm/trade-platform/refund-list"


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


async def logged_in(page):
    try:
        await page.goto(CHECK_URL, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log(f"goto 异常(继续判): {str(e)[:60]}")
    await page.wait_for_timeout(6000)
    u = page.url or ""
    ok = ("login" not in u) and ("login.taobao.com" not in u)
    log(f"当前 URL: {u[:90]} → {'已登录' if ok else '未登录'}")
    return ok


def to_add_cookie(c):
    out = {"name": c["name"], "value": c["value"], "domain": c["domain"],
           "path": c.get("path") or "/", "expires": time.time() + 30 * 86400}
    if c.get("httpOnly"):
        out["httpOnly"] = True
    out["secure"] = c.get("secure", True)
    ss = c.get("sameSite")
    if ss in ("Strict", "Lax", "None"):
        out["sameSite"] = ss
    return out


async def main():
    if not os.path.exists(BACKUP):
        log(f"没有备份文件 {BACKUP} —— 需先保存登录态")
        return 2
    data = json.load(open(BACKUP, encoding="utf-8"))
    cookies = [to_add_cookie(c) for c in data.get("cookies", []) if c.get("name") and c.get("domain")]
    log(f"备份 {len(cookies)} 个 cookie (存于 {data.get('saved_at')})")
    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    try:
        page = await ctx.new_page()
        try:
            if await logged_in(page):
                log("登录仍有效, 不注入 (避免覆盖已刷新的 cookie)")
                return 0
            log("检测到掉登录 → 注入备份 cookie (设 30 天过期以持久化)")
            await ctx.add_cookies(cookies)
            if await logged_in(page):
                log("注入成功, 已恢复登录 ✅")
                return 0
            log("注入后仍登录失败 —— 服务端会话已失效, 需人工扫码重登")
            return 3
        finally:
            await page.close()
    finally:
        await b.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
