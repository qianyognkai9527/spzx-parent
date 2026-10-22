#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mtop.1688.trading.dataline.service 直调器（sign 自算, 复用 9222 登录态 cookie）。"""
import asyncio
import hashlib
import json
import sys
import time
import urllib.parse

sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing")
from cdp_utils import connect_cdp  # noqa: E402

API = "mtop.1688.trading.dataline.service"
APPKEY = "12574478"
H5 = f"https://h5api.m.1688.com/h5/{API}/1.0/"
REFERER = "https://air.1688.com/app/ctf-page/trade-order-list/buyer-order-list.html?page=1&pageSize=10"


async def mtop_call(ctx, data_obj, tries=3, log=print):
    """调 mtop.1688.trading.dataline.service。返回解析后的 JSON dict。"""
    for attempt in range(tries):
        token = ""
        for c in await ctx.cookies("https://h5api.m.1688.com"):
            if c["name"] == "_m_h5_tk":
                token = c["value"].split("_")[0]
                break
        t = str(int(time.time() * 1000))
        data_str = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))
        sign = hashlib.md5(f"{token}&{t}&{APPKEY}&{data_str}".encode()).hexdigest()
        url = (f"{H5}?jsv=2.7.4&appKey={APPKEY}&t={t}&sign={sign}&ecode=1&type=json"
               f"&valueType=string&api={API}&v=1.0&dataType=json")
        r = await ctx.request.post(
            url, data=("data=" + urllib.parse.quote(data_str)),
            headers={"content-type": "application/x-www-form-urlencoded", "referer": REFERER},
            timeout=30000)
        body = await r.text()
        try:
            j = json.loads(body)
        except Exception:
            log(f"  非JSON响应 len={len(body)}: {body[:120]}")
            await asyncio.sleep(2)
            continue
        ret = j.get("ret") or []
        if any("SUCCESS" in x for x in ret):
            return j
        log(f"  ret={ret} (attempt {attempt + 1})")
        await asyncio.sleep(2)   # token 过期时 Set-Cookie 会刷新, 重试即用新 token
    return None


def dig_result(j):
    """响应里 result 是二次编码 JSON → 解开取 data.data(订单数组) 与外层结构。"""
    d = (j.get("data") or {}).get("data")
    if isinstance(d, dict) and isinstance(d.get("result"), str):
        try:
            return json.loads(d["result"]), d
        except Exception:
            return None, d
    return None, d


async def main():
    b, ctx = await connect_cdp(9222, keep_urls=["1688.com", "ufuwu.1688.com"], log=print)
    try:
        data = {"serviceId": "OrderListDataLineService.buyerOrderList",
                "param": json.dumps({"page": 1, "pageSize": 100}, separators=(",", ":"))}
        j = await mtop_call(ctx, data)
        if not j:
            print("调用失败")
            return
        inner, outer = dig_result(j)
        print("outer keys:", list((outer or {}).keys()))
        if inner:
            print("inner keys:", list(inner.keys()))
            dd = inner.get("data") or {}
            print("data keys:", list(dd.keys()) if isinstance(dd, dict) else type(dd).__name__)
            if isinstance(dd, dict):
                for k, v in dd.items():
                    if not isinstance(v, list):
                        print(f"  {k} = {str(v)[:120]}")
                    else:
                        print(f"  {k}: list[{len(v)}]")
            orders = dd.get("data") if isinstance(dd, dict) else None
            if orders:
                print(f"\n订单数(本页): {len(orders)}")
                for x in orders[:5] + orders[-3:]:
                    e = (x.get("orderEntries") or [{}])[0]
                    print(f"  {x['idStr']} {x.get('gmtCreate')} ¥{int(x.get('sumPayment') or 0)/100:.2f} "
                          f"运费¥{int(x.get('carriage') or 0)/100:.2f} {x.get('statusLabel')} "
                          f"offer={e.get('sourceId')} {e.get('productName','')[:14]}")
            with open("/tmp/buyer_orders_p1.json", "w", encoding="utf-8") as f:
                json.dump(inner, f, ensure_ascii=False)
            print("\n[saved] /tmp/buyer_orders_p1.json")
    finally:
        await b.close()

asyncio.run(main())
