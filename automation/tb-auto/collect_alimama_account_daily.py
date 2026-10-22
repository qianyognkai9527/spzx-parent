#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_alimama_account_daily.py — 阿里妈妈(万相台无界版)账户每日花费, 落 promo_cost_daily.

产物: 每天一行 `report_source='account'`, `plan_type='account'`, `campaign_id='account'`,
      唯一键 `(shop_id, plan_type, campaign_id, stat_date)`(见 promo_cost_daily.uk_promo_daily)。

只读: 只发查询请求, 不点任何写/提交/预算/出价按钮; 页面上下文里 fetch 借用会话级
      csrfId/loginPointId(见 collect_alimama_promo.borrow_template)。

------------------------------------------------------------------------------------------
⚠ 口径重大发现(2026-10-12 实测, 覆盖任务书假设):
  任务书原方案是「两个投放产品(onebpSearch 关键词 + onebpDisplay 人群)当日所有**现存计划**
  `charge` 之和」。实测这个方案**严重少算**, 原因是 `campaign/horizontal/findPage.json`
  只返回**当前仍存在**的计划, 而平台账户报表会把**已删除计划**的花费也算进去; 账户还投了
  第三个产品。同一段 2024-10-01~2026-09-30:
      findPage 汇总(原方案)        =  342.69
      账户全域报表(universalBP)    = 4333.93   ← 真实值
  例: 2026-08-16~22 关键词投放花了 101.00, 但那次投放的计划已删除 → findPage 当周返回 0;
      2026-06-23~08-15 账户还投了第三个产品, 全域比两产品多出 ~300。
  因此本采集器**默认走账户全域报表接口**(权威、含所有产品与已删除计划):
      POST https://one.alimama.com/report/query.json
      body: {"bizCode":"universalBP","mx_bizCode":"universalBP",
             "startTime":<day>,"endTime":<day>,"sourceList":["scene"],
             "queryFieldIn":["charge"],"splitType":"day","queryDomains":["date"], ...}
      实测该接口就是万相台账户概览页自己用的报表接口, 一次可返回区间内每天一行(≤90 天)。
  原 findPage 方案保留为 `--method findpage`(仅做对照, 已知会少算, 不建议落库)。
------------------------------------------------------------------------------------------

数据保留(实测): universalBP 报表回溯到 2026-03-27(该账户首笔花费); 更早区间接口返回空。
  **本采集器只落 API 真正返回的日期, 不返回的日期不写行**(report/query.json 只回有花费的天)——
  报表无数据 ≠ 确认无花费(可能是保留期外), 写 0 会把未知粉饰成"没花钱"、让 P&L 高估利润。
  故输出天然截断在最早真有数据的那天。某窗口接口返回 0 行时会打明确警告(可能是无数据,
  也可能是请求字段/响应结构异常), 不会当成"已覆盖"。

跑法:
  # 默认账户全域口径, 单次 ≤90 天
  automation/venv/bin/python tb-auto/collect_alimama_account_daily.py --days 5 --dry-run
  automation/venv/bin/python tb-auto/collect_alimama_account_daily.py --from 2024-10-01 --to 2024-12-29
  # 对照原 findPage 方案(会少算)
  automation/venv/bin/python tb-auto/collect_alimama_account_daily.py --from 2026-09-01 --to 2026-09-30 --method findpage --dry-run
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
sys.path.insert(0, BASE)
from collect_alimama_promo import BIZ, PORT, borrow_template, date_range, hit_risk  # noqa: E402
from pnl_common import connect_db, log, upsert_promo_account_daily  # noqa: E402
from cdp_utils import connect_cdp  # noqa: E402

PARTIAL_DAYS = 90  # 单次最多采的天数(与 date_range 上限一致)
REPORT_URL = "https://one.alimama.com/report/query.json"
ACCOUNT_BIZ = "universalBP"  # 账户全域(所有投放产品)报表的 bizCode


# ---------- 账户全域口径(默认) ----------

async def fetch_account_days(page, tpl, days):
    """一次取回区间内账户全域每日 charge(含所有产品与已删除计划)。

    `report/query.json` + splitType=day 只返回区间内**真有数据的**日期各一行;
    未返回的日期可能是当日无花费, 也可能是超出报表保留期(实测回溯到 2026-03-27)——
    调用方**不得**据此回填 0(会把"未采到/超保留期"粉饰成"确实没花钱", 让 P&L 高估利润)。
    返回 {day: round(charge,2)}, 天然截断在最早真有数据的那天。
    """
    csrf = tpl["body"].get("csrfId")
    lp = tpl["body"].get("loginPointId")
    body = {
        "bizCode": ACCOUNT_BIZ, "mx_bizCode": ACCOUNT_BIZ,
        "startTime": days[0], "endTime": days[-1],
        "sourceList": ["scene"], "queryFieldIn": ["charge"],
        "splitType": "day", "queryDomains": ["date"],
        "csrfId": csrf, "loginPointId": lp,
    }
    r = await page.evaluate("""async ([u,b]) => {
        const res = await fetch(u,{method:'POST',headers:{'content-type':'application/json'},
            body:JSON.stringify(b),credentials:'include'});
        return {status:res.status, text:await res.text()}; }""", [REPORT_URL, body])
    if hit_risk(r["text"]):
        raise RuntimeError("风控命中, 停止")
    try:
        j = json.loads(r["text"])
    except Exception:
        raise RuntimeError(f"账户报表非 JSON 响应 HTTP {r['status']}")
    info = j.get("info") or {}
    if info.get("ok") is False:
        raise RuntimeError(f"账户报表返回错误: {info.get('message')}")
    out = {}
    for row in ((j.get("data") or {}).get("list") or []):
        d = row.get("thedate")
        if d:
            out[d] = round(float(row.get("charge") or 0), 2)
    return out


# ---------- findPage 两产品口径(对照, 已知少算) ----------

async def sum_day_findpage(page, tpl, biz_code, day):
    """借页面上下文发一次 findPage(翻页汇总 charge), 返回当日 charge 合计。

    ⚠ 只含"当前仍存在"的计划 → 已删除计划的花费丢失, 账户口径会少算。仅作对照。
    """
    total = 0.0
    offset = 0
    for _ in range(30):
        body = {k: v for k, v in tpl["body"].items() if k not in ("offset", "pageSize", "statusList")}
        body.update({"bizCode": biz_code, "mx_bizCode": biz_code, "offset": offset,
                     "pageSize": 200, "statusList": ["start", "pause"],
                     "rptQuery": {"fields": "charge", "conditionList": [{
                         "sourceList": ["scene", "campaign_list"],
                         "startTime": day, "endTime": day, "isRt": False}]}})
        url = tpl["url"].split("?")[0] + "?csrfId=" + str(tpl["body"].get("csrfId")) + "&bizCode=" + biz_code
        r = await page.evaluate("""async ([u,h,b]) => {
            const res = await fetch(u,{method:'POST',headers:h,body:JSON.stringify(b),credentials:'include'});
            return {status:res.status, text:await res.text()}; }""", [url, tpl["headers"], body])
        if hit_risk(r["text"]):
            raise RuntimeError("风控命中, 停止")
        j = json.loads(r["text"])
        data = j.get("data") or {}
        lst = data.get("list") or []
        for c in lst:
            rid = c.get("reportInfoList")
            info = (rid[0] if isinstance(rid, list) and rid else rid) or {}
            if isinstance(info, dict) and info.get("charge") is not None:
                total += float(info["charge"])
        if not lst or offset + 200 >= int(data.get("count") or 0):
            break
        offset += 200
        await asyncio.sleep(1.5)
    return total


async def run(args):
    days = date_range(args.dfrom, args.dto)
    if not days:
        log(f"日期非法或超 {PARTIAL_DAYS} 天: {args.dfrom}~{args.dto}")
        return 2
    b, ctx = await connect_cdp(PORT, keep_urls=["one.alimama.com", "myseller.taobao.com", "taobao.com"], log=log)
    conn = None if args.dry_run else connect_db()
    try:
        shop_id = 0
        if conn:
            from shop_ref import default_shop_id
            with conn.cursor() as c:
                shop_id = default_shop_id(c, 1) or 0
        page = await ctx.new_page()
        try:
            # 借会话级 csrfId/loginPointId(账户报表与 findPage 共用会话)
            tpl = await borrow_template(page, "onebpSearch", days[-1])
            if not tpl:
                log("!! 没借到请求参数(登录态掉了?)")
                return 1

            written = 0
            if args.method == "account":
                by_day = await fetch_account_days(page, tpl, days)
                # 只落库 API 真正返回的日期; 不返回的日期**不写 0**(报表无数据≠确认无花费,
                # 写 0 会把"未采到/超保留期"粉饰成"确实没花钱", 让 P&L 高估利润)。
                day_charges = sorted(by_day.items())
                if not day_charges:
                    log(f"!! 警告: 账户全域报表 {args.dfrom}~{args.dto} 返回 0 行 —— "
                        f"该窗口无数据, 或请求字段/响应结构异常(未确认覆盖, 请人工核对)")
                else:
                    log(f"账户全域报表: {args.dfrom}~{args.dto} 命中 {len(day_charges)} 天; "
                        f"最早 {day_charges[0][0]} 最晚 {day_charges[-1][0]}")
                    if day_charges[0][0] != days[0]:
                        log(f"  (注: 窗口首日 {days[0]} 早于最早有数据日 {day_charges[0][0]}, "
                            f"更早日期不落行)")
            else:
                tpls = {"onebpSearch": tpl}
                tpls["onebpDisplay"] = await borrow_template(page, "onebpDisplay", days[-1])
                if not tpls["onebpDisplay"]:
                    log("!! onebpDisplay 没借到参数")
                    return 1
                day_charges = []
                for d in days:
                    charge = 0.0
                    for biz_code, _ in BIZ:
                        charge += await sum_day_findpage(page, tpls[biz_code], biz_code, d)
                    day_charges.append((d, round(charge, 2)))
                    await asyncio.sleep(1.5)

            for day, charge in day_charges:
                row = {"shop_id": shop_id, "platform_code": 1, "stat_date": day,
                       "plan_type": "account", "campaign_id": "account",
                       "campaign_name": None, "report_source": "account",
                       "charge": round(charge, 2)}
                if args.dry_run:
                    log(f"  [dry] {day} 账户花费 = {row['charge']}")
                else:
                    written += upsert_promo_account_daily(conn, row)
                    conn.commit()
                    log(f"  {day} 账户花费 = {row['charge']}  (已写 {written}/{len(day_charges)})")
            if not day_charges:
                log(f"完成[{args.method}]: 0 行, 未确认覆盖, 写入 0 (退出码 3)")
                return 3  # 覆盖未确认, 供 cron wrapper 报警(非真实成功)
            log(f"完成[{args.method}]: 覆盖 {len(day_charges)} 天 "
                f"({day_charges[0][0]}~{day_charges[-1][0]}), 写入 {written}")
        finally:
            await page.close()
    finally:
        if conn:
            conn.close()
        await b.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default=None)
    ap.add_argument("--to", dest="dto", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--days", type=int, default=0)
    ap.add_argument("--method", choices=("account", "findpage"), default="account",
                    help="account=账户全域报表(权威, 默认); findpage=两产品现存计划汇总(会少算)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.days:
        a.dfrom = (datetime.strptime(a.dto, "%Y-%m-%d").date() - timedelta(days=a.days - 1)).isoformat()
    if not a.dfrom:
        a.dfrom = (datetime.strptime(a.dto, "%Y-%m-%d").date() - timedelta(days=14)).isoformat()
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
