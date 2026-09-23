"""crawl_gold_factory.py — 抓 1688 金牌制造榜优质厂家, 标 S/SS/SSS 入 source_factory。

来源: https://sale.1688.com/factory/bd_jpzz.html (平台精挑上榜工厂, 按类目分 tab)
类目: 只抓与选品直接相关的 女装/内衣/服饰配饰。

判定:
  SSS = 上榜 + 钻级>=三钻 或 (履约率>=95% 且 回头率>=60%)
  SS  = 上榜 (金牌榜本身即优质) 或 履约率>=95%
等级覆盖: 取最高级, 低于现有 A/B 则保留原级(S/SS/SSS 均高于 A)。

用法: automation/venv/bin/python crawl_gold_factory.py [--test] [--dry]
  --test 只抓第一个类目第一页并打印, 不入库
  --dry  抓取+判级, 只打印不入库
"""
import asyncio
import json
import os
import re
import sys
import time
import pymysql
from playwright.async_api import async_playwright

CDP = "http://127.0.0.1:9223"
GOLD_URL = "https://sale.1688.com/factory/bd_jpzz.html?__existtitle__=1&__removesafearea__=1"
RAW_FILE = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/gold_factory.jsonl"
DB = {"host": "localhost", "port": 3306, "user": "root",
      "password": "root123456", "database": "db_spzx", "charset": "utf8mb4"}

# 目标类目 tab (金牌榜上的名称)
TARGET_TABS = ["女装", "内衣", "服饰配饰"]
MAX_PAGES = 12


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def grade_factory(card):
    """判级: 返回 SSS/SS/S 或 None"""
    drill = card.get('drill', 0)          # 钻级数字(一钻=1...)
    fulfill = card.get('fulfill_rate', 0)  # 履约率 0-100
    resp = card.get('resp_rate', 0)        # 响应率 0-100
    repurch = card.get('repurchase', 0)    # 回头率 0-100
    if drill >= 3 or (fulfill >= 95 and repurch >= 60):
        return "SSS"
    if fulfill >= 95:
        return "SS"
    return "SS"  # 金牌榜上榜本身即优质


async def extract_cards(page):
    """提取当前页所有工厂卡片: 以加粗公司名 <a> 为锚点, 向上找卡片容器"""
    return await page.evaluate("""() => {
        const out = [];
        // 公司名锚点: 加粗的公司链接 (font-weight bold + 以公司/厂/供应链等结尾)
        const anchors = [...document.querySelectorAll('a')].filter(a => {
            const t = (a.textContent || '').trim();
            const st = a.getAttribute('style') || '';
            return a.offsetParent !== null && t.length >= 4 && t.length <= 40
                && st.includes('font-weight: bold')
                && /有限公司|服饰|制衣|内衣|鞋厂|实业|供应链|服装/.test(t);
        });
        const seen = new Set();
        for (const a of anchors) {
            const name = (a.textContent || '').trim();
            if (seen.has(name)) continue;
            // 向上找卡片容器(含 厂房/员工)
            let card = a, ctext = '';
            for (let i = 0; i < 6; i++) {
                card = card.parentElement;
                if (!card) break;
                ctext = (card.innerText || '').replace(/\\s+/g, ' ').trim();
                if (ctext.includes('厂房') && ctext.includes('员工')) break;
            }
            if (!card || !ctext.includes('厂房')) continue;
            seen.add(name);

            // 钻级: 上榜X钻工厂 / 上榜一钻工厂
            let drill = 0;
            const dm = ctext.match(/上榜([一二三四五六七八九十\\d])钻工厂/);
            if (dm) {
                const cn = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9};
                drill = cn[dm[1]] || parseInt(dm[1]) || 1;
            }
            const ff = (ctext.match(/(\\d+)%履约率/) || [])[1] || '';
            const rr = (ctext.match(/(\\d+)%响应率/) || [])[1] || '';
            const rp = (ctext.match(/(\\d+)%回头率/) || [])[1] || '';
            const area = (ctext.match(/厂房 (\\d+)㎡/) || [])[1] || '';
            const emp = (ctext.match(/员工 (\\d+)人/) || [])[1] || '';

            out.push({
                name,
                link: a.href || '',
                fulfill_rate: ff ? parseInt(ff) : 0,
                resp_rate: rr ? parseInt(rr) : 0,
                repurchase: rp ? parseInt(rp) : 0,
                drill, area: area ? parseInt(area) : 0,
                employees: emp ? parseInt(emp) : 0
            });
        }
        return out;
    }""")


async def crawl_tab(page, tab_name, test):
    """抓单个类目 tab 的所有页"""
    # 点 tab
    clicked = await page.evaluate("""(t) => {
        const els = [...document.querySelectorAll('*')];
        const e = els.find(x => x.offsetParent !== null && x.children.length === 0
            && (x.textContent || '').trim() === t);
        if (e) { e.click(); return true; }
        return false;
    }""", tab_name)
    if not clicked:
        log(f"  ✗ 找不到 tab {tab_name}")
        return []
    await asyncio.sleep(6)

    rows = []
    max_pages = 1 if test else MAX_PAGES
    for p in range(1, max_pages + 1):
        cards = await extract_cards(page)
        for c in cards:
            c['grade'] = grade_factory(c)
            c['tab'] = tab_name
            rows.append(c)
        log(f"  [{tab_name}] 第{p}页: {len(cards)} 家")
        if p >= max_pages:
            break
        # 翻页
        nxt = await page.evaluate("""() => {
            const els = [...document.querySelectorAll('*')];
            const btn = els.find(e => e.offsetParent !== null && e.children.length === 0
                && (e.textContent || '').trim() === '下一页');
            if (btn) { btn.click(); return true; }
            return false;
        }""")
        if not nxt:
            log(f"  [{tab_name}] 无下一页, 结束")
            break
        await asyncio.sleep(5)
    return rows


def save_rows(rows):
    with open(RAW_FILE, 'a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def upsert_factory(rows):
    """按 factory_name+platform_type=1 upsert, 新等级高于现有则覆盖"""
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    ins = upd = 0
    grade_order = {'SSS': 5, 'SS': 4, 'S': 3, 'A': 2, 'B': 1}
    for r in rows:
        cur.execute("SELECT id, quality_grade FROM source_factory "
                    "WHERE factory_name=%s AND platform_type=1 AND is_deleted=0", (r['name'],))
        row = cur.fetchone()
        new_g = r['grade']
        if row:
            old_g = row[1]
            if old_g and grade_order.get(old_g, 0) >= grade_order.get(new_g, 0):
                continue  # 现有等级不低, 不动
            cur.execute("""UPDATE source_factory
                SET quality_grade=%s, avg_repurchase_rate=%s, total_sales=GREATEST(IFNULL(total_sales,0),0),
                    trust_years=GREATEST(IFNULL(trust_years,0),0), update_time=%s
                WHERE id=%s""", (new_g, r['repurchase'], now, row[0]))
            upd += 1
        else:
            cur.execute("""INSERT INTO source_factory
                (factory_name, avg_repurchase_rate, quality_grade, platform_type,
                 factory_url, create_time, is_deleted)
                VALUES (%s,%s,%s,1,%s,%s,0)""",
                (r['name'], r['repurchase'], new_g, r['link'] or '', now))
            ins += 1
    conn.commit()
    cur.close()
    conn.close()
    return ins, upd


async def main():
    test = '--test' in sys.argv
    dry = '--dry' in sys.argv

    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    page = await ctx.new_page()
    await page.goto(GOLD_URL, wait_until='domcontentloaded')
    await asyncio.sleep(10)

    all_rows = []
    tabs = TARGET_TABS[:1] if test else TARGET_TABS
    for tab in tabs:
        log(f"=== 抓取类目 {tab} ===")
        rows = await crawl_tab(page, tab, test)
        all_rows.extend(rows)

    log(f"\n抓取完成: 共 {len(all_rows)} 家厂家")
    from collections import Counter
    print("等级分布:", dict(Counter(r['grade'] for r in all_rows)))

    if dry or test:
        for r in all_rows[:15]:
            print(f"  [{r['grade']}] {r['name']} | 履约{r['fulfill_rate']}% 回头{r['repurchase']}% 钻{r['drill']}")
    else:
        save_rows(all_rows)
        ins, upd = upsert_factory(all_rows)
        log(f"入库: 新增 {ins}, 升级 {upd} -> source_factory")
    try:
        await page.close()
    except Exception:
        pass
    await b.close()


asyncio.run(main())
