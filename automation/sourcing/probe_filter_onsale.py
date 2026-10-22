#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""noon probe 2 (2026-10-19, 只读): 点「商品状态: 销售中」筛选, 抓控制台列表 API 的
完整请求 URL(含参数) + 响应体样本, 验证「列表 API 直接带货源库存/状态」假设.
产物: /tmp/noon_filter_probe.json
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from cdp_utils import connect_cdp, minimize_windows
from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli

PORT = 9222
KEEP = ["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com"]
OUT = "/tmp/noon_filter_probe.json"
WATCH = ("gw.open.1688.com", "proxy")


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


async def main():
    out = {"requests": [], "bodies": [], "after_filter_text": "", "error": None}
    b, ctx = await connect_cdp(PORT, keep_urls=KEEP, log=log)
    page = None
    try:
        try:
            await minimize_windows(ctx, log=log)
        except Exception as e:
            log(f"minimize err {e!r}")
        page = await open_page(ctx, quiet=True)
        fr = await get_frame(page)
        await nav_to_guanli(fr)
        await asyncio.sleep(3)

        captured = []

        async def on_resp(r):
            u = r.url
            if any(w in u for w in WATCH) and "mmstat" not in u:
                try:
                    body = await r.text()
                except Exception:
                    body = ""
                captured.append({"url": u, "len": len(body), "head": body[:1500]})

        page.on("response", lambda r: asyncio.create_task(on_resp(r)))

        # 找并点「商品状态: 销售中」筛选
        clicked = await fr.evaluate("""() => {
            const els = [...document.querySelectorAll('span,div,button,a,li')];
            for (const e of els) {
                const t = (e.textContent||'').replace(/\\s+/g,'');
                if ((t === '商品状态:销售中' || t === '销售中') && e.children.length <= 2) {
                    e.click(); return t;
                }
            }
            return null;
        }""")
        log(f"点击筛选: {clicked}")
        await asyncio.sleep(5)
        out["after_filter_text"] = await fr.evaluate(
            "() => (document.body.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0, 1200)")
        await asyncio.sleep(2)
        out["requests"] = captured[-8:]
        log(f"捕获 {len(captured)} 个代理响应, 取最后 {len(out['requests'])} 个")
    except Exception as e:
        out["error"] = repr(e)
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass
        try:
            await b.close()
        except Exception:
            pass
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"完成, 见 {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
