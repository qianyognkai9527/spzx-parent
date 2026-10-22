#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""noon probe (2026-10-19, 只读侦察, 12:03-12:25 静默窗口用):
A. 铺货平台「已关联货源」视图侦察: chip 文本(找在售/下架筛选) + 表头 + 样例行 + 列表 XHR 路径
B. 1688 SKU API 直连探针: 抓一次页面加载的完整请求做模板 → 同页 fetch 重放其他 offerId
   验证: 响应与页面加载一致? 延迟多少? 是否触发风控?
产物: /tmp/noon_recon.json + /tmp/sku_direct_probe.json
"""
import asyncio
import json
import re
import sys
import time

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from cdp_utils import connect_cdp, minimize_windows, new_page_quiet
from scrape_isv_offer_taobao import get_frame, open_page, nav_to_guanli

SKU_API = "mtop.1688.wosc.queryofferskuselectormodel"
RECON_OUT = "/tmp/noon_recon.json"
API_OUT = "/tmp/sku_direct_probe.json"
PORT = 9222
KEEP = ["myseller.taobao.com", "ufuwu.1688.com", "detail.1688.com"]


def log(m):
    print(f"{time.strftime('%H:%M:%S')} {m}", flush=True)


def pick_offers(n=5):
    from dbconf import DB_CONFIG
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, source_product_url FROM source_product "
                "WHERE is_deleted=0 AND source_status=1 "
                "AND source_product_url LIKE '%%detail.1688.com/offer/%%' "
                f"ORDER BY id LIMIT {int(n)}")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    out = []
    for pid, url in rows:
        m = re.search(r"offer/(\d+)", url or "")
        if m:
            out.append((int(pid), m.group(1)))
    return out


async def part_a_recon(ctx):
    out = {"chips": [], "headers": [], "rows": [], "xhr": [], "error": None}
    page = None
    try:
        page = await open_page(ctx, quiet=True)
        xhrs = set()
        page.on("request", lambda r: xhrs.add(r.url) if (".json" in r.url or "list" in r.url.lower()) else None)
        fr = await get_frame(page)
        try:
            await nav_to_guanli(fr)
        except Exception as e:
            out["nav_error"] = repr(e)
        await asyncio.sleep(4)
        out["chips"] = await fr.evaluate("""() => {
            const seen = new Set(); const out = [];
            document.querySelectorAll('span,div,button,a').forEach(e => {
                const t = (e.textContent||'').trim();
                if (t && t.length>=2 && t.length<=16 && e.children.length===0 && !seen.has(t) &&
                    /在售|出售|下架|仓库|货源|关联|铺货|状态/.test(t)) { seen.add(t); out.push(t); }
            });
            return out.slice(0, 60);
        }""")
        out["headers"] = await fr.evaluate(
            "() => [...document.querySelectorAll('th')].map(e=>(e.textContent||'').trim()).filter(Boolean).slice(0,30)")
        out["rows"] = await fr.evaluate("""() => {
            const rows = [...document.querySelectorAll('tr')].filter(r => r.querySelectorAll('td').length >= 3);
            return rows.slice(0, 2).map(r => (r.innerText||'').replace(/\\n/g,' | ').slice(0, 400));
        }""")
        out["xhr"] = sorted({u.split('?')[0] for u in xhrs if SKU_API not in u})[:40]
    except Exception as e:
        out["error"] = repr(e)
    finally:
        try:
            if page:
                await page.close()
        except Exception:
            pass
    json.dump(out, open(RECON_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"A 侦察完成 chips={len(out['chips'])} headers={len(out['headers'])} xhr={len(out['xhr'])} err={out['error']}")
    return out


def swap_offer(url, body, oid):
    nu = re.sub(r"([?&](?:offerId|offerIdLong|contentId)=)\d+", lambda m: m.group(1) + str(oid), url)
    nb = body
    if nb:
        try:
            d = json.loads(nb)
            def walk(o):
                if isinstance(o, dict):
                    for k in list(o):
                        if "offer" in k.lower() and isinstance(o[k], (str, int)) and re.fullmatch(r"\d{6,}", str(o[k])):
                            o[k] = str(oid)
                        else:
                            walk(o[k])
                elif isinstance(o, list):
                    for x in o:
                        walk(x)
            walk(d)
            nb = json.dumps(d)
        except Exception:
            nb = re.sub(r"\b\d{9,}\b", str(oid), nb)
    return nu, nb


def count_skus(body_text):
    try:
        d = json.loads(body_text)
        info = d.get("data", {}).get("skuSelectorBizModel", {}).get("skuInfoMap", {})
        return len(info) if isinstance(info, dict) else -1
    except Exception:
        return -2


async def part_b_api(ctx, offers):
    out = {"template": None, "results": [], "note": ""}
    page = await new_page_quiet(ctx, "about:blank")
    tmpl = {"url": None, "method": None, "body": None}

    async def on_req(r):
        if SKU_API in r.url and tmpl["url"] is None:
            tmpl["url"] = r.url
            tmpl["method"] = r.method
            try:
                tmpl["body"] = r.post_data
            except Exception:
                pass

    page.on("request", lambda r: asyncio.create_task(on_req(r)))
    base_body = {"n": -3}
    oid0, o0 = offers[0]
    try:
        await page.goto(f"https://detail.1688.com/offer/{o0}.html", wait_until="domcontentloaded")
        await asyncio.sleep(4)
    except Exception as e:
        out["note"] += f"goto err {e!r}; "
    out["template_captured"] = bool(tmpl["url"])
    out["template"] = {k: (v[:300] if isinstance(v, str) else v) for k, v in tmpl.items()}
    json.dump(out, open(API_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    if not tmpl["url"]:
        await page.close()
        log("B 直连探针: 未抓到 SKU API 请求模板, 放弃")
        return out

    fetch_js = """async (args) => {
        const t0 = performance.now();
        try {
            const opt = {credentials: 'include'};
            if (args.method === 'POST' && args.body) {
                opt.method = 'POST';
                opt.headers = {'content-type': 'application/json'};
                opt.body = args.body;
            }
            const r = await fetch(args.url, opt);
            const t1 = performance.now();
            const txt = await r.text();
            return {status: r.status, ms: Math.round(t1 - t0), body: txt.slice(0, 300000)};
        } catch (e) { return {error: String(e)}; }
    }"""

    for pid, oid in offers:
        url, body = swap_offer(tmpl["url"], tmpl["body"], oid)
        t0 = time.time()
        try:
            res = await asyncio.wait_for(page.evaluate(fetch_js, {"url": url, "method": tmpl["method"], "body": body}), timeout=25)
        except Exception as e:
            res = {"error": repr(e)}
        ms = int((time.time() - t0) * 1000)
        n = count_skus(res.get("body", "")) if isinstance(res, dict) and "body" in res else -1
        if oid == o0:
            base_body = {"n": count_skus(res.get("body", "")) if "body" in res else -1}
        out["results"].append({"pid": pid, "offer": oid, "ms_direct": ms, "sku_count": n,
                               "status": res.get("status") if isinstance(res, dict) else None,
                               "err": res.get("error") if isinstance(res, dict) else None})
        log(f"B offer={oid} ms={ms} sku={n}")
        await asyncio.sleep(5)
    out["baseline_oid0"] = base_body
    await page.close()
    json.dump(out, open(API_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"B 直连探针完成 baseline={base_body} 见 {API_OUT}")
    return out


async def main():
    offers = pick_offers(5)
    log(f"探针 offer 样本: {[o[1] for o in offers]}")
    if not offers:
        log("无样本, 退出")
        return
    b, ctx = await connect_cdp(PORT, keep_urls=KEEP, log=log)
    try:
        await minimize_windows(ctx, log=log)
    except Exception as e:
        log(f"minimize err {e!r}")
    try:
        await asyncio.wait_for(part_a_recon(ctx), timeout=90)
        await asyncio.wait_for(part_b_api(ctx, offers), timeout=180)
    except Exception as e:
        log(f"探针异常: {e!r}")
    finally:
        try:
            await b.close()
        except Exception:
            pass
    log("全部探针结束")


if __name__ == "__main__":
    asyncio.run(main())
