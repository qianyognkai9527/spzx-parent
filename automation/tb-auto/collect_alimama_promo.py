#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_alimama_promo.py — 采集阿里妈妈(万相台无界版)推广计划日报, 落 promo_cost_daily.

为什么不走导出: 报表导出实测拿不到; 而报表页的数据本来就是接口给的 ——
`campaign/horizontal/findPage.json` 带 rptQuery, 一次返回区间内**全部计划 + 指标**。
指标字典取自 `component/findList.json`(页面渲染表头用的就是它), 共 31 项。

鉴权: csrfId / loginPointId 是会话级的, cookie 又是 httpOnly 拿不全,
      所以必须**在页面上下文里发 fetch** —— 打开管理页借一次真实请求的参数, 再改日期重放。

只读: 只调查询接口, 不点按钮, 不碰出价/预算/计划开关。

口径三条(都实测过, 不是猜的):
1. ctr/cvr/cartRate/itemColInshopRate 接口给的是**比值**(0.03869), 表里存百分数 → ×100。
2. reportInfoList 为 null 表示"当天没有任何投放数据", 与"报表给了 0"是两回事 → 跳过并计数, 不写一行 NULL。
3. 成交类指标有**归因回补**, 同一 stat_date 隔天会变 → 默认滚动重拉 15 天, 靠唯一键 upsert 覆盖。

跑法: automation/venv/bin/python collect_alimama_promo.py --days 15
     automation/venv/bin/python collect_alimama_promo.py --from 2026-09-20 --to 2026-10-02 --dry-run
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
from cdp_utils import connect_cdp  # noqa: E402
from cron_batch import DB_CONFIG, begin_batch, end_batch  # noqa: E402
import pymysql  # noqa: E402

PORT = 9222
BASE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE, "alimama_promo_raw")
DATASET = "promo_cost"
DATASET_DETAIL = "promo_cost_detail"
ADGROUP_URL = "https://one.alimama.com/adgroup/horizontal/findPage.json"
PLATFORM_CODE = 1  # 淘宝

# 两个推广产品: bizCode → 我们表里的 plan_type
BIZ = [("onebpSearch", "keyword"), ("onebpDisplay", "crowd")]
MANAGE_PAGE = {
    "onebpSearch": "https://one.alimama.com/index.html#!/manage/search?mx_bizCode=onebpSearch"
                   "&bizCode=onebpSearch&startTime={d}&endTime={d}",
    "onebpDisplay": "https://one.alimama.com/index.html#!/manage/display?mx_bizCode=onebpDisplay"
                    "&bizCode=onebpDisplay&startTime={d}&endTime={d}",
}
# 接口字段 → (表列, 类型)。类型 pct=比值×100 / money=两位 / rate=四位小数 / int
FIELD_MAP = [
    ("charge", "charge", "money"),
    ("adPv", "ad_pv", "int"),
    ("click", "click", "int"),
    ("ctr", "ctr_percent", "pct"),
    ("ecpc", "cpc", "rate"),
    ("ecpm", "cpm", "rate"),
    ("alipayInshopAmt", "gmv_total", "money"),
    ("alipayDirAmt", "gmv_direct", "money"),
    ("alipayIndirAmt", "gmv_indirect", "money"),
    ("alipayInshopNum", "order_total", "int"),
    ("alipayDirNum", "order_direct", "int"),
    ("alipayIndirNum", "order_indirect", "int"),
    ("roi", "roi", "money"),
    ("cvr", "cvr_percent", "pct"),
    ("alipayInshopCost", "order_cost", "rate"),
    ("cartInshopNum", "cart_count", "int"),
    ("cartDirNum", "cart_direct", "int"),
    ("cartIndirNum", "cart_indirect", "int"),
    ("cartRate", "cart_rate_percent", "pct"),
    ("cartCost", "cart_cost", "rate"),
    ("itemColInshopNum", "item_collect", "int"),
    ("shopColDirNum", "shop_collect", "int"),
    ("colNum", "collect_total", "int"),
    ("itemColInshopRate", "item_collect_rate_percent", "pct"),
    ("itemColInshopCost", "item_collect_cost", "rate"),
    ("shopColInshopCost", "shop_collect_cost", "rate"),
    ("colCartNum", "collect_cart_total", "int"),
    ("colCartCost", "collect_cart_cost", "rate"),
    ("itemColCart", "item_collect_cart", "int"),
    ("itemColCartCost", "item_collect_cart_cost", "rate"),
    ("shoppingAmt", "shopping_amt", "money"),
    ("addNewUv", "add_new_uv", "int"),
]
# successRatio 页面 fields 里出现过但语义没证出来, 故意不采 —— 猜一个成本率字段进表比不采更糟
FIELDS_STR = ",".join(f for f, _, _ in FIELD_MAP)
# 标准计划的判据: 接口 bidType。custom_bid≈标准计划(手动出价), roi_control≈智能控投产
STANDARD_BID_TYPES = ("custom_bid",)
MAX_PAGES = 25  # 宝贝层分页上限：507 单元 / 200 一页 = 3 页，25 页是防失控的保险丝
RISK_WORDS = ("RGV587", "x5sec", "captchacappuzzle", "FAIL_SYS_USER_VALIDATE", "被挤爆")
UPSERT_COLS = [c for _, c, _ in FIELD_MAP]


def log(m):
    print(f"[{time.strftime('%F %T')}] {m}", flush=True)


# ---------- 纯函数 ----------

def cast(v, kind):
    """按列类型转换。None 原样返回 None(表里 NULL=不知道), 不要塌成 0。

    用 Decimal ROUND_HALF_UP 而不是内置 round(): round 是银行家舍入,
    11.86215 会得 11.8621; 而 Java 侧 PromoRowConverter 用的是 HALF_UP(11.8622)。
    两条写入路径(CSV 导入 / 接口采集)对同一份数据必须落同一个值, 否则重导会"改数据"。
    """
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        return None
    if kind == "int":
        return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if kind == "pct":
        d = d * 100          # 先放大再定点, 反过来会先把比值的有效位削掉
    places = "0.01" if kind == "money" else "0.0001"
    return float(d.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def is_standard(bid_type, only_standard=True):
    if not only_standard:
        return True
    return (bid_type or "") in STANDARD_BID_TYPES


def date_range(dfrom, dto):
    """闭区间逐日。起止反了或超 90 天视为参数错, 返回 []。"""
    try:
        a = datetime.strptime(dfrom, "%Y-%m-%d").date()
        b = datetime.strptime(dto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return []
    if a > b or (b - a).days > 90:
        return []
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def map_row(campaign, stat_date, plan_type, shop_id, report_source):
    """一个计划节点 → 一行 promo_cost_daily(dict)。

    返回 (row, reason): row=None 时 reason 说明为什么不要这行。
    reportInfoList 为 null 是"当天没有任何投放数据", 与给了 0 是两回事 ——
    写一行全 NULL 的记录只会让看板把"没采到"显示成"没花钱"。
    """
    rid = campaign.get("reportInfoList")
    if not rid:
        return None, "no_report"
    info = rid[0] if isinstance(rid, list) else rid
    if not isinstance(info, dict):
        return None, "bad_report"
    cid = campaign.get("campaignId")
    if cid is None:
        return None, "no_id"
    row = {
        "shop_id": shop_id if shop_id is not None else 0,
        "platform_code": PLATFORM_CODE,
        "stat_date": stat_date,
        "plan_type": plan_type,
        "campaign_id": str(cid),
        "campaign_name": campaign.get("campaignName"),
        "report_source": report_source,
        "bid_type": campaign.get("bidType"),
    }
    for src, col, kind in FIELD_MAP:
        row[col] = cast(info.get(src), kind)
    row["raw_json"] = json.dumps(info, ensure_ascii=False)
    return row, None


def hit_risk(text):
    t = text or ""
    return next((w for w in RISK_WORDS if w in t), None)


def item_id_of(adgroup):
    """单元 → 宝贝 ID。万相台关键词推广里「单元」就是「宝贝」，adgroupName 直接是商品标题。

    优先 material.materialId（13 位，与 platform_product.code 同形，实测可 join 上），
    退而求其次 bindItemId / parentItemId，都没有就用 adgroupId 占位并让 entity_name 保住标题。
    """
    mat = adgroup.get("material") or {}
    for k in ("materialId", "bindItemId", "parentItemId"):
        v = mat.get(k)
        if v:
            return str(v)
    return str(adgroup.get("adgroupId") or "")


def map_adgroup_row(adgroup, stat_date, plan_type, shop_id, report_source):
    """一个单元(=宝贝)节点 → 一行 promo_cost_item_daily。

    与计划层同一套字段名，所以复用 FIELD_MAP。
    reportInfoList 里**没有 charge 键**表示当天该宝贝没有任何投放数据 —— 一个 507 单元的
    计划里通常只有十几个宝贝当天有数，其余只回一个 roi7d。这种行不写，
    否则表里会堆满"看着是 0 其实是没数据"的行，把付费/免费对比彻底带偏。
    """
    rl = adgroup.get("reportInfoList")
    info = rl[0] if isinstance(rl, list) and rl else None
    if not isinstance(info, dict) or "charge" not in info:
        return None, "no_data"
    cid = adgroup.get("campaignId")
    if cid is None:
        return None, "no_campaign"
    item_id = item_id_of(adgroup)
    if not item_id:
        return None, "no_item_id"
    title = adgroup.get("adgroupName")
    row = {
        "shop_id": shop_id if shop_id is not None else 0,
        "platform_code": PLATFORM_CODE,
        "stat_date": stat_date,
        "plan_type": plan_type,
        "dimension": "item",
        "entity_key": item_id,
        "entity_id": str(adgroup.get("adgroupId") or ""),
        "entity_name": title,
        "item_id": item_id,
        "item_name": title,
        # 唯一键含 campaign_id，NULL 之间不算重复 → 空串兜底
        "campaign_id": str(cid),
        "campaign_name": adgroup.get("campaignName"),
        "unit_id": str(adgroup.get("adgroupId") or ""),
        "unit_name": title,
        "report_source": report_source,
        "raw_json": json.dumps(info, ensure_ascii=False),
    }
    for src, col, kind in FIELD_MAP:
        row[col] = cast(info.get(src), kind)
    return row, None


def should_page(count, page_size):
    """分页偏移列表：count 个单元按 page_size 翻完要取的 offset。"""
    try:
        total, size = int(count), max(1, int(page_size))
    except (TypeError, ValueError):
        return [0]
    if total <= 0:
        return [0]
    return list(range(0, ((total - 1) // size + 1) * size, size))


# ---------- 采集 ----------

def connect_db():
    """连接配置复用 cron_batch，不在这个文件里再抄一份明文凭据。"""
    return pymysql.connect(**DB_CONFIG)


def upsert(conn, table, cols, rows, batch_tag):
    """按各表的自然键 upsert。列清单显式传进来，不给默认值——
    两张表键不同（计划表 4 列、明细表 5 列），猜错会把重复行堆进事实表。"""
    if not rows:
        return 0
    ph = ",".join(["%s"] * len(cols))
    key_cols = {"promo_cost_daily": ("shop_id", "plan_type", "campaign_id", "stat_date"),
                "promo_cost_item_daily": ("shop_id", "dimension", "entity_key", "campaign_id", "stat_date")}
    if table not in key_cols:
        raise ValueError(f"未知的目标表 {table}")
    upd = ",".join(f"{c}=new.{c}" for c in cols if c not in key_cols[table])
    sql = (f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) AS new "
           f"ON DUPLICATE KEY UPDATE {upd}")
    cur = conn.cursor()
    for r in rows:
        cur.execute(sql, tuple([r.get(c) for c in cols[:-1]] + [batch_tag]))
    conn.commit()
    return len(rows)


DAILY_COLS = (["shop_id", "platform_code", "stat_date", "plan_type", "campaign_id",
               "campaign_name", "report_source", "bid_type"] + UPSERT_COLS + ["raw_json", "import_batch"])
ITEM_COLS = (["shop_id", "platform_code", "stat_date", "plan_type", "dimension", "entity_key",
              "entity_id", "entity_name", "item_id", "item_name", "campaign_id", "campaign_name",
              "unit_id", "unit_name", "report_source"] + UPSERT_COLS + ["raw_json", "import_batch"])


async def borrow_template(page, biz_code, day):
    """把 page 开到该产品的管理页, 借一次真实 findPage 请求的 url/headers/csrfId/loginPointId.

    **page 必须保持存活且停在 one.alimama.com 源上**：fetch 是在它的上下文里发的,
    换成 about:blank 就成跨域, 直接 "Failed to fetch"。
    """
    tpl = {}

    async def on_req(req):
        if tpl or "campaign/horizontal/findPage.json" not in req.url:
            return
        try:
            body = json.loads(req.post_data or "{}")
        except Exception:
            return
        if "csrfId" not in body:
            return
        tpl["url"] = req.url
        tpl["body"] = body
        tpl["headers"] = {k: v for k, v in (req.headers or {}).items()
                          if k.lower() in ("content-type", "accept", "bx-v")}

    page.on("request", on_req)
    url = MANAGE_PAGE[biz_code].format(d=day)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log(f"goto 异常(继续等): {str(e)[:70]}")
    for _ in range(24):
        await asyncio.sleep(1.5)
        if tpl:
            break
    return tpl


async def fetch_day(page, tpl, biz_code, day):
    body = {k: v for k, v in tpl["body"].items() if k not in ("offset", "pageSize", "statusList")}
    body["bizCode"] = biz_code
    body["mx_bizCode"] = biz_code
    body["offset"] = 0
    body["pageSize"] = 200
    body["statusList"] = ["start", "pause"]
    body["adgroupRequired"] = False
    body["adzoneRequired"] = False
    body["rptQuery"] = {
        "fields": FIELDS_STR,
        "conditionList": [{"sourceList": ["scene", "campaign_list"],
                           "startTime": day, "endTime": day, "isRt": False}],
    }
    url = tpl["url"].split("?")[0] + "?csrfId=" + str(tpl["body"].get("csrfId")) + "&bizCode=" + biz_code
    r = await page.evaluate("""async ([u, h, b]) => {
        const res = await fetch(u, {method:'POST', headers:h, body:JSON.stringify(b), credentials:'include'});
        return {status: res.status, text: await res.text()};
    }""", [url, tpl["headers"], body])
    return r["status"], r["text"]


async def fetch_adgroups(page, tpl, biz_code, campaign_id, day, offset, page_size):
    """计划×日×宝贝：POST adgroup/horizontal/findPage.json.

    sourceList 必须放在 rptQuery.conditionList 里面（["campaign_detail","adgroup_list"]）——
    放在请求体顶层接口会直接忽略，返回的还是计划汇总，这是这一层最费时间的坑。
    """
    body = {
        "offset": offset, "pageSize": page_size, "orderField": "", "orderBy": "",
        "bizCode": biz_code, "mx_bizCode": biz_code,
        "campaignIdList": [str(campaign_id)],
        "requestSource": "campaignAdgroupHorizontal",
        "adgroupRequired": False, "adzoneRequired": False,
        "rptQuery": {"fields": FIELDS_STR, "conditionList": [{
            "sourceList": ["campaign_detail", "adgroup_list"],
            "startTime": day, "endTime": day, "isRt": False}]},
        "csrfId": tpl["body"].get("csrfId"),
        "loginPointId": tpl["body"].get("loginPointId"),
    }
    url = ADGROUP_URL + "?csrfId=" + str(tpl["body"].get("csrfId")) + "&bizCode=" + biz_code
    r = await page.evaluate("""async ([u, h, b]) => {
        const res = await fetch(u, {method:'POST', headers:h, body:JSON.stringify(b), credentials:'include'});
        return {status: res.status, text: await res.text()};
    }""", [url, tpl["headers"], body])
    return r["status"], r["text"]


async def collect_items(page, tpl, biz_code, campaign_id, day, args, plan_type):
    """按计划翻完所有单元(=宝贝)。返回 (可入库的行, 扫到的单元总数, 翻了几页)。

    第一页的 data.count 决定要翻几页；一个 507 单元的计划里通常只有十几个宝贝当天有数，
    所以"扫到的单元数"和"写入库的行数"差一个量级是正常的，不是漏采。
    """
    rows, seen, offset, pages = [], 0, 0, 0
    while pages < MAX_PAGES:
        status, text = await fetch_adgroups(page, tpl, biz_code, campaign_id, day,
                                            offset, args.page_size)
        if hit_risk(text):
            errors_note = f"{biz_code} {day} 计划{campaign_id} 宝贝层命中风控"
            log("!! " + errors_note)
            break
        try:
            j = json.loads(text)
        except Exception:
            log(f"  宝贝层非 JSON 响应 HTTP {status} offset={offset}")
            break
        data = j.get("data") or {}
        lst = data.get("list") or []
        seen += len(lst)
        for a in lst:
            row, _reason = map_adgroup_row(a, day, plan_type, args.shop_id,
                                           f"alimama-adgroup:{biz_code}")
            if row is not None:
                rows.append(row)
        with open(os.path.join(RAW_DIR, f"items_{plan_type}_{campaign_id}_{day}_{offset}.json"),
                  "w", encoding="utf-8") as f:
            f.write(text)
        pages += 1
        count = data.get("count") or seen
        if offset + args.page_size >= int(count) or not lst:
            break
        offset += args.page_size
        await asyncio.sleep(args.gap)
    return rows, seen, pages


async def run(args):
    os.makedirs(RAW_DIR, exist_ok=True)
    days = date_range(args.dfrom, args.dto)
    if not days:
        log(f"日期区间非法或超过 90 天: {args.dfrom}~{args.dto}")
        return 2
    log(f"待采 {len(days)} 天 × {len(BIZ)} 个推广产品；标准计划判据 bidType∈{STANDARD_BID_TYPES}")

    b, ctx = await connect_cdp(PORT, keep_urls=["taobao.com", "1688.com", "alimama.com"], log=log)
    conn = None if args.dry_run else connect_db()
    batch_tag = f"alimama-{time.strftime('%Y%m%d%H%M%S')}"
    # dry-run 不进台账：台账是"数据已落库"的唯一凭据，记一条 success 但表里没行，
    # 新鲜度判定就会把"没采到"当成"刚采过"，30 小时 SLA 永远不告警。
    bid = None if args.dry_run else begin_batch(
        DATASET, channel="api", platform=PLATFORM_CODE, biz_from=days[0], biz_to=days[-1])
    bid_item = None if (args.dry_run or args.level == "campaign") else begin_batch(
        DATASET_DETAIL, channel="api", platform=PLATFORM_CODE, biz_from=days[0], biz_to=days[-1])
    total = ok = skipped_noreport = skipped_bidtype = failed = 0
    item_total = item_ok = 0
    errors = []
    drift = []
    early_return = None
    try:
        for biz_code, plan_type in BIZ:
            page = await ctx.new_page()
            try:
                # 同一张页面负责"借参数"和"发请求"：换页就丢了 alimama 源, fetch 会变跨域
                tpl = await borrow_template(page, biz_code, days[-1])
                if not tpl:
                    msg = f"{biz_code} 没借到 findPage 请求参数(登录态掉了?)"
                    log("!! " + msg)
                    errors.append(msg)
                    failed += len(days)
                    continue
                for day in days:
                    status, text = await fetch_day(page, tpl, biz_code, day)
                    risk = hit_risk(text)
                    if risk:
                        msg = f"{biz_code} {day} 命中风控关键字 {risk}"
                        log("!! " + msg)
                        errors.append(msg)
                        early_return = 42
                        break
                    try:
                        j = json.loads(text)
                    except Exception:
                        errors.append(f"{biz_code} {day} 非 JSON 响应 HTTP {status}")
                        failed += 1
                        continue
                    lst = ((j.get("data") or {}).get("list")) or []
                    rows = []
                    for c in lst:
                        total += 1
                        if not is_standard(c.get("bidType"), not args.all_bid_types):
                            skipped_bidtype += 1
                            continue
                        row, reason = map_row(c, day, plan_type, args.shop_id, batch_tag)
                        if row is None:
                            skipped_noreport += 1
                            continue
                        rows.append(row)
                    if rows:
                        if args.dry_run:
                            ok += len(rows)
                            for r in rows[:2]:
                                log(f"  [dry] {day} {plan_type} {r['campaign_name']} "
                                    f"花费={r['charge']} 展现={r['ad_pv']} 点击={r['click']} "
                                    f"ctr%={r['ctr_percent']} 加购={r['cart_count']}")
                        else:
                            ok += upsert(conn, "promo_cost_daily", DAILY_COLS, rows, batch_tag)
                    with open(os.path.join(RAW_DIR, f"{plan_type}_{day}.json"), "w",
                              encoding="utf-8") as f:
                        f.write(text)
                    log(f"{plan_type} {day}: 计划{len(lst)} 写入{len(rows)} "
                        f"无投放数据{sum(1 for c in lst if not c.get('reportInfoList'))}")
                    await asyncio.sleep(args.gap)

                    # 宝贝粒度：只对"当天确实花了钱"的标准计划下钻，其余计划没有可归因的东西
                    if args.level not in ("item", "both"):
                        continue
                    plan_charge = {r["campaign_id"]: r["charge"] for r in rows}
                    for cid in plan_charge:
                        item_rows, cnt, pages = await collect_items(
                            page, tpl, biz_code, cid, day, args, plan_type)
                        item_total += cnt
                        for r in item_rows:
                            r["import_batch"] = batch_tag
                        if item_rows:
                            if args.dry_run:
                                item_ok += len(item_rows)
                            else:
                                item_ok += upsert(conn, "promo_cost_item_daily", ITEM_COLS,
                                                  item_rows, batch_tag)
                        # 自证完整性：宝贝花费之和应当等于计划花费（同一接口同一天的两层）
                        s = sum(r["charge"] or 0 for r in item_rows)
                        want = plan_charge[cid] or 0
                        verdict = "OK" if abs(s - want) < 0.05 else f"差 {round(s - want, 2)}"
                        log(f"    宝贝 {cid}: 有数{len(item_rows)}/{cnt} 页{pages} "
                            f"Σ花费 {round(s, 2)} vs 计划 {want} → {verdict}")
                        if abs(s - want) >= 0.05:
                            # 这是平台侧归因口径的差, 不是采集失败：开了 wholeSite(全站/智能扩量)
                            # 的计划, 那部分花费与流量不落到任何具体单元。实测 09-15 差 0.20 元
                            # /7 展现/1 点击, 09-16 差 0.80/3/1 —— 三个指标成比例, 所以是同一批流量。
                            # 记进台账当数据质量注记，但**不算作业失败**，否则 cron 每天误报一次。
                            drift.append(f"{day} {plan_type} 计划{cid}: 宝贝合计{round(s,2)}"
                                         f"/计划{want} 差{round(s - want, 2)}")
                        await asyncio.sleep(args.gap)
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
            if early_return is not None:
                break
    except Exception as e:
        # 任何异常都不能把台账留在 running —— 那行假状态要等 12 小时才被扫成 failed
        errors.append(f"未捕获异常: {str(e)[:200]}")
        log(f"!! {errors[-1]}")
        early_return = 1
    finally:
        status = ("failed" if early_return == 42 else
                  "success" if (not errors and failed == 0 and ok and not drift) else
                  "partial" if ok else "failed")
        note = "; ".join((errors + drift)[:5]) or None
        end_batch(bid, status, rows_total=total, rows_ok=ok, rows_invalid=skipped_noreport,
                  error=note)
        if bid_item:
            ist = ("failed" if early_return == 42 else
                   "success" if (not errors and item_ok and not drift) else
                   "partial" if item_ok else "failed")
            end_batch(bid_item, ist, rows_total=item_total, rows_ok=item_ok, error=note)
        if conn:
            conn.close()
        await b.close()

    log(f"\n完成[{status}]: 计划层 扫到 {total} 写入 {ok} (非标准计划跳过 {skipped_bidtype}, "
        f"当天无投放数据 {skipped_noreport}, 失败 {failed})")
    if args.level in ("item", "both"):
        log(f"              宝贝层 扫到 {item_total} 写入 {item_ok}")
    if drift:
        log(f"归因偏差 {len(drift)} 处(平台侧全站/智能扩量流量不落单元, 非采集失败): "
            + "; ".join(drift[:5]))
    if errors:
        log("错误样本: " + "; ".join(errors[:5]))
    # 退出码只表达"作业成没成"：有行落库且无真错误就是 0，归因偏差不该让 cron 每天误报
    if early_return is not None:
        return early_return
    return 0 if (ok and not errors and failed == 0) else 1

    status = "success" if not errors and failed == 0 else ("partial" if ok else "failed")
    end_batch(bid, status, rows_total=total, rows_ok=ok, rows_invalid=skipped_noreport,
              error=("; ".join(errors[:5]) or None))
    log(f"\n完成: 扫到计划行 {total}, 写入 {ok}, 非标准计划跳过 {skipped_bidtype}, "
        f"当天无投放数据 {skipped_noreport}, 失败 {failed}")
    if errors:
        log("错误样本: " + "; ".join(errors[:5]))
    return 0 if status == "success" else 1


def main():
    ap = argparse.ArgumentParser()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    ap.add_argument("--to", dest="dto", default=yesterday)
    ap.add_argument("--from", dest="dfrom", default=None, help="默认 = to 往前 14 天(共 15 天滚动窗口)")
    ap.add_argument("--days", type=int, default=0, help="快捷: 只采最近 N 天")
    ap.add_argument("--shop-id", type=int, default=None)
    ap.add_argument("--gap", type=float, default=4.0, help="两次查询之间的间隔秒数")
    ap.add_argument("--level", choices=("campaign", "item", "both"), default="campaign",
                    help="campaign=只采计划日报 item=只采宝贝粒度 both=两层都采")
    ap.add_argument("--page-size", type=int, default=200, help="宝贝层分页大小")
    ap.add_argument("--all-bid-types", action="store_true", help="不只采 custom_bid(标准计划)")
    ap.add_argument("--dry-run", action="store_true", help="只采集打印, 不写库也不进台账")
    a = ap.parse_args()
    if a.days:
        a.dto = a.dto or yesterday
        a.dfrom = (datetime.strptime(a.dto, "%Y-%m-%d").date() - timedelta(days=a.days - 1)).isoformat()
    if not a.dfrom:
        a.dfrom = (datetime.strptime(a.dto, "%Y-%m-%d").date() - timedelta(days=14)).isoformat()
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
