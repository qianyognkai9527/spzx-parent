"""爬取抖店后台订单, 落库到 db_spzx.order_info (platform_type=2)。

前置: 9223 Chrome 已登录抖店后台 (fxg.jinritemai.com)。
用法: /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python crawl_douyin_orders.py [--test]
  --test: 只读订单总数, 不翻页不落库

注意: 抖店订单页为 React SPA, 订单行结构可能随平台改版变化;
      行解析基于表头 [商品信息/单价数量/售后状态/订单状态/商家收入金额/收货信息/操作] 的当前布局,
      有真实订单时需目视校验一次解析结果。
"""
import asyncio
import re
import sys
import time
import pymysql
from shop_ref import default_shop_id, PLATFORM_DOUYIN

CDP = "http://127.0.0.1:9223"
ORDER_URL = "https://fxg.jinritemai.com/ffa/morder/order/list"
DB = {"host": "localhost", "port": 3306, "user": "root",
      "password": "root123456", "database": "db_spzx", "charset": "utf8mb4"}

STATUS_MAP = {"待支付": 0, "待发货": 1, "已发货": 2, "已完成": 3, "已取消": -1,
              "待付款": 0, "部分发货": 2, "关闭": -1}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def get_order_page(ctx):
    for p in ctx.pages:
        if "morder/order/list" in p.url:
            return p
    p = await ctx.new_page()
    await p.goto(ORDER_URL, wait_until="domcontentloaded", timeout=45000)
    await p.wait_for_timeout(8000)
    return p


async def read_total(p):
    m = await p.evaluate(
        "() => { const m = document.body.innerText.match(/全部订单?(\\d+)/); return m ? parseInt(m[1]) : -1; }")
    return m


async def extract_orders(p):
    js = r"""
    () => {
      const rows = Array.from(document.querySelectorAll('table tbody tr'));
      const out = [];
      for (const tr of rows) {
        const t = tr.innerText || '';
        if (!t || t.indexOf('暂无数据') > -1) continue;
        const cells = Array.from(tr.querySelectorAll('td'));
        const idm = t.match(/\b\d{15,20}\b/);
        const orderNo = idm ? idm[0] : '';
        if (!orderNo) continue;
        let status = '';
        for (const k of ['待支付','待付款','待发货','已发货','部分发货','已完成','已取消','关闭']) {
          if (t.indexOf(k) > -1) { status = k; break; }
        }
        const amtM = t.match(/[￥¥]\s*([0-9]+\.?[0-9]*)/);
        const amount = amtM ? amtM[1] : '';
        out.push({orderNo, status, amount, raw: t.slice(0, 300)});
      }
      return out;
    }
    """
    return await p.evaluate(js)


async def crawl(test_mode=False):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.connect_over_cdp(CDP)
        try:
            ctx = b.contexts[0]
            p = await get_order_page(ctx)
            total = await read_total(p)
            log(f"抖店订单总数: {total}")
            if total <= 0:
                log("无订单, 结束")
                return 0
            if test_mode:
                log("--test 模式, 不爬取落库")
                return 0

            all_orders = []
            all_orders.extend(await extract_orders(p))
            log(f"第1页采集 {len(all_orders)} 个")

            page_num = 2
            while len(all_orders) < total and page_num <= 50:
                jumped = await p.evaluate("""(n) => {
                  const li = [...document.querySelectorAll('li')]
                    .find(x => x.textContent.trim() === String(n) && x.className.includes('pagination-item'));
                  if (!li) return false; li.click(); return true;
                }""", page_num)
                if not jumped:
                    log(f"翻到第{page_num}页失败, 停止")
                    break
                await p.wait_for_timeout(2500)
                batch = await extract_orders(p)
                if not batch:
                    log(f"第{page_num}页 0 个, 停止")
                    break
                all_orders.extend(batch)
                log(f"第{page_num}页采集 {len(batch)} 个 (累计 {len(all_orders)})")
                page_num += 1

            log(f"采集完成: 共 {len(all_orders)} 个订单")

            conn = pymysql.connect(**DB)
            cur = conn.cursor()
            ins = 0
            shop_id = default_shop_id(cur, PLATFORM_DOUYIN)
            for o in all_orders:
                order_no = o["orderNo"]
                cur.execute("SELECT id FROM order_info WHERE order_no=%s AND platform_type=2", (order_no,))
                if cur.fetchone():
                    continue
                status = STATUS_MAP.get(o["status"], 0)
                amt = float(o["amount"]) if o["amount"] else 0
                cur.execute("""INSERT INTO order_info
                    (order_no, order_status, total_amount, platform_type, shop_id, is_deleted, create_time, update_time)
                    VALUES (%s,%s,%s,2,%s,0,NOW(),NOW())""",
                            (order_no, status, amt, shop_id))
                ins += 1
            conn.commit()
            cur.close()
            conn.close()
            log(f"落库完成: 新增 {ins} 条 (重复跳过 {len(all_orders)-ins})")
            return ins
        finally:
            await b.close()


if __name__ == "__main__":
    test = "--test" in sys.argv
    n = asyncio.run(crawl(test_mode=test))
    log(f"done: {n}")
