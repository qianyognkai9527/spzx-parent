#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生意参谋 商品排行 数据快照 (2026-09-07)

抓取 sycm.taobao.com/cc/item_rank 商品效果数据(免费版):
访客数/浏览量/加购人数/收藏人数 → 入库 sycm_item_effect_history
用途: 爆品初筛(加购率/访客Top) + 每日快照积累增速数据

用法:
  --probe            仅抓1页并打印首条数据结构(摸字段用)
  --date-type TYPE   today / recent7(默认) / recent30
  --max-pages N      最多翻页数(默认 999)
  --page-size N      每页条数尝试(默认先试100)

退出码: 0=成功 42=风控(RGV587,需冷却) 1=错误
"""
import asyncio
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing")
from cdp_utils import connect_cdp  # noqa: E402

import pymysql  # noqa: E402

PAGE_URL = "https://sycm.taobao.com/cc/item_rank"
API_MARK = "/cc/item/view/top.json"

DB = dict(host="localhost", user="root", password="root123456",
          database="db_spzx", charset="utf8mb4")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def ensure_guard_tab(port=9222):
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/new?{urllib.parse.quote('https://www.taobao.com')}",
            method="PUT")
        urllib.request.urlopen(req, timeout=5)
        log("已补开守卫标签")
    except Exception as e:
        log(f"守卫标签补开失败: {e}")


def extract_query(url, key):
    m = re.search(rf"[?&]{key}=([^&]+)", urllib.parse.unquote(url))
    return m.group(1) if m else ""


def find_item_list(obj, depth=0):
    """递归找元素数>0且首元素为dict的数据数组(取最长)"""
    best = None
    if depth > 6:
        return best
    if isinstance(obj, dict):
        for v in obj.values():
            r = find_item_list(v, depth + 1)
            if r and (best is None or len(r) > len(best)):
                best = r
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        best = obj
        for v in obj[:2]:
            r = find_item_list(v, depth + 1)
            if r and len(r) > len(best):
                best = r
    return best


def _v(d, *keys):
    """按候选键取嵌套 {value: x} 的值"""
    for k in keys:
        if k in d and isinstance(d[k], dict):
            return d[k].get("value", 0)
    return 0


def parse_items(items, date_type, date_range):
    """解析 top.json 条目 (2026-09-07 实测结构: item{} + 各指标 {value,cycleCrc,syncCrc})"""
    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        meta = it.get("item") or {}
        iid = meta.get("itemId") or _v(it, "itemId", "mainProductId")
        if not iid:
            continue
        rows.append(dict(
            item_id=str(iid),
            title=(str(meta.get("title") or ""))[:250],
            date_type=date_type,
            date_range=date_range,
            visitors=int(_v(it, "itmUv") or 0),
            page_views=int(_v(it, "itmPv") or 0),
            cart_users=int(_v(it, "crtByrCnt") or 0),
            cart_items=int(_v(it, "itemCartCnt") or 0),
            cart_rate=float(_v(it, "crtRate") or 0),
            fav_users=int(_v(it, "itemCltByrCnt") or 0),
            fav_rate=float(_v(it, "visitCltRate") or 0),
            pay_byrs=int(_v(it, "payByrCnt") or 0),
            pay_amt=float(_v(it, "payAmt") or 0),
            pay_rate=float(_v(it, "payRate") or 0),
            stay_sec=float(_v(it, "stayTimeAvg") or 0),
            bounce_rate=float(_v(it, "itmBounceRate") or 0),
            se_uv=int(_v(it, "seGuideUv") or 0),
            item_status=str(it.get("itemStatus") or "")[:30],
            item_no=str(meta.get("itemNO") or "")[:100],
            cate_id=str(_v(it, "cateId") or meta.get("categoryId") or "")[:30],
            extra=json.dumps(it, ensure_ascii=False)[:20000],
        ))
    return rows


def save_db(rows):
    if not rows:
        return 0
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sql = """INSERT INTO sycm_item_effect_history
                     (item_id,title,date_type,date_range,visitors,page_views,
                      cart_users,cart_items,cart_rate,fav_users,fav_rate,
                      pay_byrs,pay_amt,pay_rate,stay_sec,bounce_rate,se_uv,
                      item_status,item_no,cate_id,extra_json,snapshot_time)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            cur.executemany(sql, [(
                r["item_id"], r["title"], r["date_type"], r["date_range"],
                r["visitors"], r["page_views"], r["cart_users"], r["cart_items"],
                r["cart_rate"], r["fav_users"], r["fav_rate"], r["pay_byrs"],
                r["pay_amt"], r["pay_rate"], r["stay_sec"], r["bounce_rate"],
                r["se_uv"], r["item_status"], r["item_no"], r["cate_id"],
                r["extra"], now) for r in rows])
        conn.commit()
        return len(rows)
    finally:
        conn.close()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--date-type", default="recent7")
    ap.add_argument("--max-pages", type=int, default=999)
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--test", action="store_true", help="只抓前3页")
    args = ap.parse_args()

    max_pages = min(args.max_pages, 3) if args.test else args.max_pages
    b, ctx = await connect_cdp(9222, keep_urls=["sycm.taobao.com"], log=log)
    pg = await ctx.new_page()

    captured = {}

    async def on_resp(r):
        u = r.url
        if API_MARK in u and "punish" not in u:
            try:
                body = await r.text()
                if "rgv587_flag" in body:
                    captured["risk"] = body
                else:
                    captured[u] = body
            except Exception:
                pass

    pg.on("response", lambda r: asyncio.ensure_future(on_resp(r)))

    url = f"{PAGE_URL}?dateType={args.date_type}"
    try:
        await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"goto异常(继续等XHR): {str(e)[:80]}")

    # 等首次数据
    for _ in range(25):
        if captured:
            break
        await pg.wait_for_timeout(1000)

    if "risk" in captured and not [u for u in captured if u != "risk"]:
        log("风控拦截(RGV587) — 退出等冷却")
        await pg.close()
        ensure_guard_tab()
        await b.close()
        return 42
    if not [u for u in captured if u != "risk"]:
        log("未捕获数据接口响应")
        await pg.screenshot(path="/tmp/sycm_noapi.png")
        await pg.close()
        ensure_guard_tab()
        await b.close()
        return 1

    first_url = [u for u in captured if u != "risk"][0]
    body = captured[first_url]
    date_range = extract_query(first_url, "dateRange") or args.date_type

    try:
        j = json.loads(body)
    except Exception:
        log(f"响应非JSON: {body[:120]}")
        await pg.close()
        ensure_guard_tab()
        await b.close()
        return 1

    items = find_item_list(j)
    if not items:
        log("响应中未找到数据数组, 结构: " + json.dumps(j, ensure_ascii=False)[:500])
        await pg.close()
        ensure_guard_tab()
        await b.close()
        return 1

    log(f"首页数据 {len(items)} 条 (url pageSize={extract_query(first_url,'pageSize')})")

    if args.probe:
        print("=== 首条数据结构:")
        print(json.dumps(items[0], ensure_ascii=False, indent=1)[:2500])
        await pg.close()
        ensure_guard_tab()
        await b.close()
        return 0

    all_rows = parse_items(items, args.date_type, date_range)
    processed = {first_url}
    page_no = 1
    risk_hit = False
    while page_no < max_pages:
        page_no += 1
        try:
            nxt = pg.locator("li.ant-pagination-next").first
            cls = await nxt.get_attribute("class") or ""
            if "ant-pagination-disabled" in cls:
                log("已到最后一页")
                break
            await nxt.click(timeout=6000)
        except Exception:
            log("找不到下一页按钮, 结束翻页")
            break
        # 等新 URL 的响应
        new_url = None
        for _ in range(15):
            await pg.wait_for_timeout(1000)
            fresh = [u for u in captured if u != "risk" and u not in processed]
            if fresh:
                new_url = fresh[0]
                break
        if not new_url:
            if "risk" in captured:
                log("翻页触发风控, 保存已有数据后退出")
                risk_hit = True
            else:
                log("翻页无新响应, 结束")
            break
        processed.add(new_url)
        try:
            j2 = json.loads(captured[new_url])
            items2 = find_item_list(j2)
            rows2 = parse_items(items2, args.date_type, extract_query(new_url, "dateRange") or date_range)
            log(f"第{page_no}页 {len(rows2)} 条")
            all_rows += rows2
        except Exception as e:
            log(f"第{page_no}页解析失败: {str(e)[:60]}")
        # 人类节奏
        await pg.wait_for_timeout(2500 + (page_no % 3) * 800)
        if page_no % 10 == 0:
            log("休息 20s 降频…")
            await pg.wait_for_timeout(20000)

    # 按 item_id+date_type 去重(同快照内)
    uniq = {}
    for r in all_rows:
        uniq[(r["item_id"], r["date_type"])] = r
    all_rows = list(uniq.values())
    n = save_db(all_rows)
    log(f"入库 {n} 条 (页数={page_no})")
    # 摘要: 加购人数Top10
    top = sorted(all_rows, key=lambda r: r["cart_users"], reverse=True)[:10]
    for r in top:
        rate = (r["cart_users"] / r["visitors"] * 100) if r["visitors"] else 0
        log(f"  加购Top: {r['item_id']} 加购={r['cart_users']} 访客={r['visitors']} 率={rate:.1f}% {r['title'][:24]}")

    await pg.close()
    ensure_guard_tab()
    await b.close()
    if risk_hit:
        return 42
    return 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc if isinstance(rc, int) else 0)
