"""1688 选品 第一阶段 v2:抗反爬版
- 慢节奏(15-25s/页)
- 触发限流(0 卡)自动冷却 COOLDOWN 秒后重试
- 进度续跑(sourcing_progress.json),中断/限流后重跑自动跳过已完成
- 崩溃安全:每张卡实时追加到 sourcing_raw.jsonl
- 最后汇总成 xlsx

用法:
  venv/bin/python source_1688.py                 # 续跑(跳过已完成,默认全量)
  venv/bin/python source_1688.py --kw 睡衣 --pages 5   # 单词
  venv/bin/python source_1688.py --test          # 1 词 1 页
  venv/bin/python source_1688.py --finalize      # 只用已采 JSONL 生成 xlsx,不爬
"""
import asyncio
import random
import re
import sys
import os
import json
import time
from urllib.parse import quote
from playwright.async_api import async_playwright
from openpyxl import Workbook

from source_config import (
    CDP_URL, CATEGORIES, MIN_TRUST_YEARS, MAX_PAGES_PER_KW, MIN_PRICE,
    PAGE_DELAY_MIN, PAGE_DELAY_MAX, SCROLL_TIMES, SCROLL_WAIT, PAGE_LOAD_WAIT, OUT_DIR,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(BASE_DIR, "sourcing_raw.jsonl")
PROGRESS_FILE = os.path.join(BASE_DIR, "sourcing_progress.json")
SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={kw}&beginPage={page}"

# 抗反爬参数
COOLDOWN = 1500          # 触发限流后冷却秒数(约 25 分钟)
MAX_RETRY = 2            # 限流重试次数
PROACTIVE_BURST = 4      # 每成功 N 页主动小憩
PROACTIVE_PAUSE = 90     # 主动小憩秒数
INTER_KW_PAUSE = 30      # 关键词之间暂停


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            return json.load(open(PROGRESS_FILE, encoding='utf-8'))
        except Exception:
            pass
    return {"done": [], "failed_kw": []}


def save_progress(prog):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=1)


def append_cards(cards):
    with open(RAW_FILE, 'a', encoding='utf-8') as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def load_all_raw():
    rows = []
    if os.path.exists(RAW_FILE):
        with open(RAW_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


async def extract_cards(page):
    return await page.evaluate(
        r"""() => {
            const els = Array.from(document.querySelectorAll('a.search-offer-wrapper.cardui-normal'));
            const out = [];
            for (const card of els) {
                const href = card.href || card.getAttribute('href') || '';
                const m = href.match(/offerId=(\d+)/);
                const offerId = m ? m[1] : '';
                const txt = (card.innerText || '').replace(/\s+/g, ' ').trim();
                const price = (txt.match(/¥\s*([\d.]+)/) || [])[1] || '';
                const sales = (txt.match(/全网(\d+\+?件)/) || [])[1] || '';
                const repurchase = (txt.match(/回头率\s*(\d+%)/) || [])[1] || '';
                let trustYears = 0;
                for (const e of card.querySelectorAll('*')) {
                    if (e.children.length === 0) {
                        const t = (e.textContent || '').trim();
                        const mm = t.match(/^(\d{1,2})年$/);
                        if (mm) { trustYears = parseInt(mm[1]); break; }
                    }
                }
                let company = '';
                const cEl = card.querySelector('[class*="ompany"],[class*="hop-name"]');
                if (cEl) company = (cEl.innerText || '').trim();
                if (!company) {
                    const idx = txt.lastIndexOf('回头率');
                    if (idx >= 0) company = txt.substring(idx).replace(/^回头率\s*\d+%\s*/, '').trim().substring(0, 50);
                }
                const title = (txt.split('¥')[0] || '').trim().substring(0, 80);
                let headImgUrl = '';
                const img = card.querySelector('img.main-img');
                if (img) headImgUrl = img.currentSrc || img.src || img.getAttribute('data-src') || '';
                out.push({offerId, title, price, sales, repurchase, trustYears, company, headImgUrl,
                          detailUrl: offerId ? ('https://detail.1688.com/offer/' + offerId + '.html') : ''});
            }
            return out;
        }"""
    )


async def crawl_one_page(page, kw, pgnum, log):
    url = SEARCH_URL.format(kw=quote(kw.encode('gbk')), page=pgnum)
    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    await asyncio.sleep(PAGE_LOAD_WAIT)
    for _ in range(SCROLL_TIMES):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(SCROLL_WAIT)
    cards = await extract_cards(page)
    cards = [c for c in cards if c['offerId']]

    # 抽样详情页检测优质标识: 每页前3个不同公司进详情页看 五星供应链/超级工厂/全球供
    # 命中则给同公司卡片打 supply_badge (补漏金牌榜未覆盖的优质厂家)
    seen_co = set()
    checked = 0
    for c in cards:
        co = c.get('company') or ''
        if not co or co in seen_co:
            continue
        seen_co.add(co)
        if checked >= 3:
            break
        checked += 1
        badge = await probe_detail_badge(page, c.get('detailUrl') or '', log)
        if badge:
            # 给该公司的所有卡片打标
            for cc in cards:
                if cc.get('company') == co:
                    cc['supply_badge'] = badge
            log(f"  ⭐ 抽样命中 [{badge}] {co}")
    return cards


async def probe_detail_badge(page, detail_url, log):
    """进详情页检测 .shop-data 区的 五星供应链/超级工厂/全球供 标识"""
    if not detail_url:
        return ''
    try:
        await page.goto(detail_url, wait_until='domcontentloaded', timeout=40000)
        await asyncio.sleep(2)
        txt = await page.evaluate("""() => {
            const el = document.querySelector('.shop-data');
            return el ? (el.innerText || '') : (document.body.innerText || '');
        }""")
    except Exception:
        return ''
    for badge in ('五星供应链', '超级工厂', '全球供'):
        if badge in txt:
            return badge
    return ''



async def crawl_keyword(page, category, kw, max_pages, prog, log):
    since_burst = 0
    for pg in range(1, max_pages + 1):
        key = f"{category}|{kw}|{pg}"
        if key in prog["done"]:
            log(f"[{category}/{kw}] 第 {pg} 页 已完成,跳过")
            continue

        log(f"[{category}/{kw}] 第 {pg}/{max_pages} 页 ...")
        cards = []
        for attempt in range(MAX_RETRY + 1):
            try:
                cards = await crawl_one_page(page, kw, pg, log)
            except Exception as e:
                log(f"  异常: {e}")
                cards = []
            if cards:
                break
            # 0 卡 → 限流
            if attempt < MAX_RETRY:
                log(f"  ⚠️ 0 卡,疑似限流,冷却 {COOLDOWN}s 后重试({attempt+1}/{MAX_RETRY})")
                await asyncio.sleep(COOLDOWN)
            else:
                log(f"  ⚠️ 仍 0 卡,放弃该词剩余页")
                if pg == 1:
                    prog["failed_kw"].append(f"{category}/{kw}")
                    save_progress(prog)
                return

        for c in cards:
            c['category'] = category
            c['keyword'] = kw
        # 类目最低价过滤:低于阈值的低价商品(退货运费亏钱)不入库
        min_p = MIN_PRICE.get(category, 0)
        if min_p > 0:
            before = len(cards)
            kept = []
            for c in cards:
                try:
                    if float(c.get('price') or 0) >= min_p:
                        kept.append(c)
                except (TypeError, ValueError):
                    pass
            cards = kept
            if before != len(cards):
                log(f"  价格过滤: {before} -> {len(cards)} (≥¥{min_p})")
        append_cards(cards)
        prog["done"].append(key)
        save_progress(prog)
        log(f"  抓到 {len(cards)} 个(累计key {len(prog['done'])})")
        since_burst += 1

        if since_burst >= PROACTIVE_BURST:
            log(f"  主动小憩 {PROACTIVE_PAUSE}s 抗限流")
            await asyncio.sleep(PROACTIVE_PAUSE)
            since_burst = 0
        else:
            await asyncio.sleep(random.uniform(PAGE_DELAY_MIN, PAGE_DELAY_MAX))


def parse_sales_num(s):
    m = re.match(r'(\d+)', s or '')
    return int(m.group(1)) if m else 0


def repurchase_num(s):
    m = re.match(r'(\d+)', s or '')
    return int(m.group(1)) if m else 0


def write_xlsx(all_rows, out_path):
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "商品候选"
    ws1.append(["类目", "关键词", "商品ID", "商品详情页链接", "标题", "价格",
                "全网销量", "回头率", "诚信通年限", "供应商", "优质标识"])
    for r in all_rows:
        ws1.append([r.get('category'), r.get('keyword'), r.get('offerId'), r.get('detailUrl'),
                    r.get('title'), r.get('price'), r.get('sales'), r.get('repurchase'),
                    r.get('trustYears'), r.get('company'), r.get('supply_badge', '')])

    ws2 = wb.create_sheet("工厂排行榜")
    by_company = {}
    for r in all_rows:
        name = r.get('company') or '(未知供应商)'
        d = by_company.setdefault(name, {'cat': r.get('category'), 'years': 0, 'count': 0,
                                          'rep_sum': 0, 'rep_n': 0, 'sales_sum': 0,
                                          'rep_offerid': '', 'rep_url': ''})
        d['years'] = max(d['years'], r.get('trustYears') or 0)
        d['count'] += 1
        rn = repurchase_num(r.get('repurchase'))
        if rn:
            d['rep_sum'] += rn
            d['rep_n'] += 1
        d['sales_sum'] += parse_sales_num(r.get('sales'))
        if not d['rep_offerid'] and r.get('offerId'):
            d['rep_offerid'] = r.get('offerId')
            d['rep_url'] = r.get('detailUrl')
    ws2.append(["供应商", "类目", "诚信通年限", "商品数", "平均回头率", "总销量(件)",
                "代表商品ID", "代表商品链接"])
    rows_sorted = sorted(by_company.items(),
                         key=lambda kv: ((kv[1]['rep_sum'] / kv[1]['rep_n']) if kv[1]['rep_n'] else 0, kv[1]['count']),
                         reverse=True)
    for name, d in rows_sorted:
        avg_rep = round(d['rep_sum'] / d['rep_n'], 1) if d['rep_n'] else 0
        ws2.append([name, d['cat'], d['years'], d['count'], f"{avg_rep}%",
                    d['sales_sum'], d['rep_offerid'], d['rep_url']])
    wb.save(out_path)


async def main():
    args = sys.argv[1:]
    test_mode = '--test' in args
    finalize = '--finalize' in args
    single_kw = None
    max_pages = MAX_PAGES_PER_KW
    if '--kw' in args:
        i = args.index('--kw')
        single_kw = args[i + 1] if i + 1 < len(args) else None
    if '--pages' in args:
        i = args.index('--pages')
        max_pages = int(args[i + 1]) if i + 1 < len(args) else max_pages
    if test_mode:
        single_kw = "睡衣"
        max_pages = 1

    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)

    if finalize:
        all_rows = load_all_raw()
        filtered = [r for r in all_rows if (r.get('trustYears') or 0) >= MIN_TRUST_YEARS]
        filtered.sort(key=lambda r: repurchase_num(r.get('repurchase')), reverse=True)
        out = os.path.join(OUT_DIR, f"sourcing_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")
        write_xlsx(filtered, out)
        log(f"✅ 仅汇总:原始 {len(all_rows)} 条,筛后 {len(filtered)} 条 -> {out}")
        return

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]
        page = None
        for pg in ctx.pages:
            if '1688' in pg.url:
                page = pg
                break
        if not page:
            page = await ctx.new_page()
        log(f"使用页面: {page.url[:60]}")

        prog = load_progress()
        log(f"进度:已完成 {len(prog['done'])} 页,失败词 {len(prog['failed_kw'])} 个")

        if single_kw:
            cat = next((c for c, kws in CATEGORIES.items() if single_kw in kws), "自定义")
            await crawl_keyword(page, cat, single_kw, max_pages, prog, log)
        else:
            for cat, kws in CATEGORIES.items():
                for kw in kws:
                    await crawl_keyword(page, cat, kw, max_pages, prog, log)
                    await asyncio.sleep(INTER_KW_PAUSE)

        all_rows = load_all_raw()
        filtered = [r for r in all_rows if (r.get('trustYears') or 0) >= MIN_TRUST_YEARS]
        filtered.sort(key=lambda r: repurchase_num(r.get('repurchase')), reverse=True)
        out = os.path.join(OUT_DIR, f"sourcing_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")
        write_xlsx(filtered, out)
        log(f"✅ 采集结束:原始 {len(all_rows)} 条,筛后 {len(filtered)} 条 -> {out}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
