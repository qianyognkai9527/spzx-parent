# 真实盈亏采集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 2024-10 ~ 2026-09 的淘宝订单、1688 代发单、阿里妈妈账户每日花费采下来落库 `db_spzx`，并产出"无 1688 关联单 = 刷单"的候选清单。

**Architecture:** 三个只读 Playwright collector（都连 9222 窗口模式 Chrome）+ 一个纯 DB 分析脚本。共用一个 `pnl_common.py`（纯解析/映射函数 + 直连库的幂等写入器），纯函数用 assert 自检脚本覆盖（沿用 `test_alimama_map.py` 的既有约定，不引入 pytest）。所有落库走 `dbconf.DB_CONFIG`，店铺归属走 `shop_ref.default_shop_id`。

**Tech Stack:** Python 3.9 / `automation/venv/bin/python`、Playwright async API、pymysql、MySQL `db_spzx`。

## Global Constraints

- **纯只读平台**：只读页面 / 翻页 / 打字设条件；绝不点「提交 / 导出 / 打单 / 退款 / 采购 / 上架」等任何写操作按钮。阿里妈妈沿用 `collect_alimama_promo.py` 的只读查询接口方式。
- **只连 9222**：一律 `from cdp_utils import connect_cdp` 且 `connect_cdp(9222, keep_urls=[...], log=log)`；**禁裸 `connect_over_cdp`**。用完 `page.close()`。
- Chrome 必须**窗口模式 + 屏外**（`--window-position=-32000,-32000`）；headless 会掉淘宝登录态、不弹窗打扰用户。
- Python 3.9，解释器 `automation/venv/bin/python`；`sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))` 才能 import `cdp_utils` / `dbconf` / `shop_ref` / `cron_batch`。
- 落库直连 `db_spzx`：`from dbconf import DB_CONFIG`（**懒连接，import 期绝不连库**）；淘宝 platform_type=1；店铺 id 用 `shop_ref.default_shop_id(cur, 1)`，取不到时按 0 兜底。
- 所有落库幂等（自然键 upsert / 先查后写）。
- **刷单阶段一不写 `brush_order`**，只出清单。
- **不提交 git**，除非用户明确要求（本机全局红线）。计划里的 commit 步骤默认不执行。
- 脚本停止后不得留下 9222 上多余的孤儿标签。

---

### Task 1: 共享纯函数与落库写入器 `pnl_common.py`

**Files:**
- Create: `automation/tb-auto/pnl_common.py`
- Test: `automation/tb-auto/test_pnl_common.py`

**Interfaces:**
- Consumes: `dbconf.DB_CONFIG`（sourcing）、`shop_ref.default_shop_id`（sourcing）。
- Produces（后续三个 collector 全部依赖，签名必须一致）：
  - `log(msg)`
  - `parse_money(s) -> Decimal | None`
  - `parse_int(s) -> int | None`
  - `parse_dt(s) -> str | None`（返回 `"YYYY-MM-DD HH:MM:SS"` 字符串，供 pymysql 直接插入）
  - `map_trade_status(text) -> int`
  - `map_purch_status(text) -> int`
  - `quarter_windows(dfrom, dto) -> list[tuple[str, str]]`
  - `parse_sold_cells(cells: list[str]) -> dict | None`
  - `build_order_info_row(parsed: dict, shop_id) -> dict`
  - `build_order_item_row(parsed: dict) -> dict`
  - `parse_isv_row(shop_order_no, source_product_id, tacobao_title, raw) -> dict`（返回 dict，见下）
  - `build_source_relation_row(isv: dict) -> dict`
  - `brush_candidates(order_rows: list[dict], related_order_nos: set) -> list[dict]`
  - `connect_db()`
  - `upsert_order_info(conn, row) -> int`（返回 `order_info.id`）
  - `upsert_order_item(conn, order_id, item) -> int`
  - `upsert_source_relation(conn, row) -> int`
  - `upsert_promo_account_daily(conn, row) -> int`

- [ ] **Step 1: 写失败的自检测试 `test_pnl_common.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pnl_common 纯函数自检. 跑法: automation/venv/bin/python tb-auto/test_pnl_common.py"""
from decimal import Decimal
from pnl_common import (brush_candidates, build_order_info_row, build_order_item_row,
                        build_source_relation_row, map_purch_status, map_trade_status,
                        parse_dt, parse_int, parse_money, parse_sold_cells,
                        quarter_windows)

# ---- NULL 保持 NULL，不塌成 0 ----
assert parse_money("¥69.90") == Decimal("69.90")
assert parse_money("￥69.90（含运费￥0.00）") == Decimal("69.90")
assert parse_money("实收款￥0.00") == Decimal("0.00")
assert parse_money(None) is None and parse_money("") is None and parse_money("无") is None
assert parse_int("x1") == 1 and parse_int("1,234") == 1234
assert parse_int("") is None and parse_int("abc") is None
assert parse_dt("2024-10-05 12:34:56") == "2024-10-05 12:34:56"
assert parse_dt("2024-10-05 12:34:56 \n买家：t**") == "2024-10-05 12:34:56"
assert parse_dt("没有时间") is None

# ---- 状态映射 ----
assert map_trade_status("交易成功") == 3
assert map_trade_status("交易关闭 详情") == -1
assert map_trade_status("等待买家付款") == 0
assert map_trade_status("卖家已发货") == 2
assert map_trade_status("") == 0
assert map_purch_status("采购单状态 已成功") == 3
assert map_purch_status("已关闭") == -1
assert map_purch_status("待打单") == 1
assert map_purch_status("退款中") == -1

# ---- 3 个月窗口 ----
w = quarter_windows("2024-10-01", "2026-07-14")
assert len(w) == 8, w
assert w[0] == ("2024-10-01", "2024-12-31")
assert w[1] == ("2025-01-01", "2025-03-31")
assert w[6] == ("2026-04-01", "2026-06-30")
assert w[7] == ("2026-07-01", "2026-07-14")   # 末端被 dto 截断
assert quarter_windows("2024-10-01", "2024-10-05") == [("2024-10-01", "2024-10-05")]

# ---- 淘宝行解析（8 个有效 td）----
CELLS = ["",
         "订单号：3234787251801271563\n2024-10-05 12:34:56\n买家：t**",
         "秋冬加绒睡裙 粉色 M\n颜色分类：粉色；尺码：M\n商家编码：ABC123",
         "¥69.90", "x1", "退款成功", "交易成功 详情", "实收款￥69.90"]
p = parse_sold_cells(CELLS)
assert p["order_no"] == "3234787251801271563", p
assert p["create_time"] == "2024-10-05 12:34:56"
assert p["unit_price"] == Decimal("69.90")
assert p["qty"] == 1
assert p["after_sale_status"] == "退款成功"
assert p["trade_status"] == "交易成功"
assert p["real_pay"] == Decimal("69.90")
assert parse_sold_cells(["", "没有订单号"]) is None

oi = build_order_info_row(p, shop_id=7)
assert oi["order_no"] == "3234787251801271563"
assert oi["order_status"] == 3
assert oi["total_amount"] == Decimal("69.90")
assert oi["platform_type"] == 1 and oi["shop_id"] == 7
assert oi["create_time"] == "2024-10-05 12:34:56"
assert "退款成功" in oi["remark"] and len(oi["remark"]) <= 500

it = build_order_item_row(p)
assert it["sku_price"] == Decimal("69.90") and it["sku_num"] == 1
assert it["platform_type"] == 1

# ---- 1688 行解析 ----
isv = {"shop_order_no": "3234787251801271563", "source_order_no": "5060020214474601936",
       "source_product_id": "810276543210", "taobao_title": "秋冬加绒睡裙",
       "taobao_price": Decimal("69.90"), "purch_amount": Decimal("32.50"),
       "source_freight": Decimal("0.00"), "purch_status": "已成功",
       "order_time": "2024-10-05 13:00:00", "remark": "买家备注：尽快发"}
sr = build_source_relation_row(isv)
assert sr["order_no"] == "3234787251801271563"
assert sr["source_order_no"] == "5060020214474601936"
assert sr["platform_type"] == 1
assert sr["order_status"] == 3
assert sr["source_selling_price"] == Decimal("32.50")
assert sr["source_freight"] == Decimal("0.00")
assert sr["order_time"] == "2024-10-05 13:00:00"

# ---- 刷单判定：有淘宝单、无 1688 关联 ----
orders = [{"order_no": "A", "create_time": "2024-10-05 12:00:00",
           "total_amount": Decimal("69.90"), "trade_status": "交易成功"},
          {"order_no": "B", "create_time": "2024-10-06 12:00:00",
           "total_amount": Decimal("59.00"), "trade_status": "交易成功"}]
cand = brush_candidates(orders, {"A"})
assert [c["order_no"] for c in cand] == ["B"]

print("test_pnl_common: ALL PASS")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation && venv/bin/python tb-auto/test_pnl_common.py`
Expected: `ModuleNotFoundError: No module named 'pnl_common'`

- [ ] **Step 3: 实现 `pnl_common.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实盈亏采集共用: 解析 / 状态映射 / 时间窗口 / 幂等落库写入器。

只读平台, 直连 db_spzx。DB_CONFIG 懒连接: import 期不碰库。
"""
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sourcing")))
import pymysql  # noqa: E402
from dbconf import DB_CONFIG  # noqa: E402

PLATFORM_TAOBAO = 1

TRADE_STATUS_MAP = (
    ("交易成功", 3), ("交易关闭", -1), ("等待买家付款", 0), ("待付款", 0),
    ("卖家已发货", 2), ("已发货", 2), ("等待卖家发货", 1), ("待发货", 1), ("交易中", 1),
)
PURCH_STATUS_MAP = (
    ("已成功", 3), ("已完成", 3), ("已发货", 2),
    ("待发货", 1), ("待打单", 1), ("待采购", 1),
    ("退款中", -1), ("已关闭", -1), ("已取消", -1),
)
MONEY_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
DT_RE = re.compile(r"(20\d\d-\d\d-\d\d \d\d:\d\d:\d\d)")
ORDER_NO_RE = re.compile(r"(\d{15,20})")
FREIGHT_RE = re.compile(r"含运费\s*[￥¥]?\s*([0-9]+(?:\.[0-9]+)?)")


def log(msg):
    print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


def parse_money(s):
    if s is None:
        return None
    m = MONEY_RE.search(str(s))
    return Decimal(m.group(1)) if m else None


def parse_int(s):
    if s is None:
        return None
    m = MONEY_RE.search(str(s).replace(",", ""))
    return int(Decimal(m.group(1))) if m else None


def parse_dt(s):
    if not s:
        return None
    m = DT_RE.search(str(s))
    return m.group(1) if m else None


def _map(text, table, default):
    t = text or ""
    for k, v in table:
        if k in t:
            return v
    return default


def map_trade_status(text):
    return _map(text, TRADE_STATUS_MAP, 0)


def map_purch_status(text):
    return _map(text, PURCH_STATUS_MAP, 0)


def _add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def quarter_windows(dfrom, dto):
    """从 dfrom 起按 3 个自然月切窗, 末窗被 dto 截断。返回 [(start, end), ...]。"""
    start = datetime.strptime(dfrom, "%Y-%m-%d").date()
    end = datetime.strptime(dto, "%Y-%m-%d").date()
    if start > end:
        return []
    out, cur = [], start
    while cur <= end:
        w_end = min(_add_months(cur, 3) - timedelta(days=1), end)
        out.append((cur.isoformat(), w_end.isoformat()))
        cur = _add_months(cur, 3)
    return out


def parse_sold_cells(cells):
    """淘宝已卖出宝贝一行 (8 个有效 td) → 解析 dict; 无订单号返回 None。"""
    if not cells or len(cells) < 8:
        return None
    head = cells[1] or ""
    m = ORDER_NO_RE.search(head)
    if not m:
        return None
    body = cells[2] or ""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    title = lines[0] if lines else None
    sku = "；".join(ln for ln in lines[1:] if not ln.startswith("商家编码"))
    return {
        "order_no": m.group(1),
        "create_time": parse_dt(head),
        "title": title,
        "sku_name": (sku or None),
        "unit_price": parse_money(cells[3]),
        "qty": parse_int(cells[4]),
        "after_sale_status": (cells[5] or "").strip() or None,
        "trade_status": (cells[6] or "").strip(),
        "real_pay": parse_money(cells[7]),
    }


def build_order_info_row(p, shop_id):
    remark = None
    if p.get("after_sale_status"):
        remark = f"履约/售后状态={p['after_sale_status']}"[:500]
    return {
        "order_no": p["order_no"],
        "order_status": map_trade_status(p.get("trade_status")),
        "total_amount": p["real_pay"] if p["real_pay"] is not None else Decimal("0.00"),
        "original_total_amount": p["real_pay"] if p["real_pay"] is not None else Decimal("0.00"),
        "receiver_name": None,
        "receiver_phone": None,
        "receiver_address": None,
        "remark": remark,
        "platform_type": PLATFORM_TAOBAO,
        "shop_id": shop_id if shop_id is not None else 0,
        "create_time": p.get("create_time"),
    }


def build_order_item_row(p):
    return {
        "sku_name": p.get("sku_name"),
        "sku_price": p["unit_price"],
        "sku_num": p["qty"],
        "platform_type": PLATFORM_TAOBAO,
    }


def parse_isv_row(shop_order_no, source_product_id, taobao_title, raw):
    """ISV 一行 → dict。source_order_no(1688 采购单号) 找不到时留 None, 由写入器跳过并计数。"""
    so = re.search(r"采购单号[：:]?\s*(\d{6,})", raw or "")
    return {
        "shop_order_no": shop_order_no,
        "source_order_no": so.group(1) if so else None,
        "order_time": parse_dt(raw),
        "source_product_id": source_product_id,
        "taobao_title": taobao_title,
        "taobao_price": parse_money(re.search(r"[￥¥]\s*[0-9.]+\s*(?=采购|$|规格)", raw or "") and
                                     (re.search(r"[￥¥]\s*[0-9.]+", raw or "") or [None])),
        "purch_amount": parse_money(re.search(r"[￥¥]\s*[0-9.]+(?=\s*（含运费)", raw or "")),
        "source_freight": parse_money(FREIGHT_RE.search(raw or "")) if FREIGHT_RE.search(raw or "") else None,
        "purch_status": _map(raw, PURCH_STATUS_MAP, "") or None,
        "remark": None,
    }


def build_source_relation_row(isv):
    return {
        "order_no": isv["shop_order_no"],
        "source_order_no": isv.get("source_order_no"),
        "platform_type": PLATFORM_TAOBAO,
        "platform_product_id": None,
        "platform_product_code": None,
        "platform_product_title": isv.get("taobao_title"),
        "platform_selling_price": isv.get("taobao_price"),
        "platform_freight": None,
        "source_product_id": (int(isv["source_product_id"])
                              if str(isv.get("source_product_id") or "").isdigit() else None),
        "source_product_code": None,
        "source_product_title": isv.get("taobao_title"),
        "source_selling_price": isv.get("purch_amount"),
        "source_freight": isv.get("source_freight"),
        "order_status": map_purch_status(isv.get("purch_status")),
        "order_time": isv.get("order_time"),
        "remark": isv.get("remark"),
    }


def brush_candidates(order_rows, related_order_nos):
    return [r for r in order_rows if r["order_no"] not in related_order_nos]


def connect_db():
    return pymysql.connect(**DB_CONFIG)


def upsert_order_info(conn, row):
    """按 uk_order_no(order_no) upsert, 返回 order_info.id。"""
    cols = ["order_no", "order_status", "total_amount", "original_total_amount",
            "receiver_name", "receiver_phone", "receiver_address", "remark",
            "platform_type", "shop_id"]
    ph = ",".join(["%s"] * (len(cols) + 2))
    upd = ",".join(f"{c}=VALUES({c})" for c in cols if c != "order_no")
    extra = ",create_time,update_time" if row.get("create_time") else ",update_time"
    vals = [(datetime.strptime(row["create_time"], "%Y-%m-%d %H:%M:%S")
             if row.get("create_time") else None)]
    if not row.get("create_time"):
        extra = ",update_time"
    sql = (f"INSERT INTO order_info ({','.join(cols + ['create_time'] + ['update_time'])}) "
           f"VALUES ({ph}) ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        cur.execute(sql, [row[c] for c in cols]
                    + [row.get("create_time"), datetime.now()])
        cur.execute("SELECT id FROM order_info WHERE order_no=%s", (row["order_no"],))
        return cur.fetchone()[0]


def upsert_order_item(conn, order_id, item):
    """order_item 无自然唯一键 → 先查后写, 幂等键 (order_id, sku_name)。"""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM order_item WHERE order_id=%s AND sku_name<=>%s",
                    (order_id, item.get("sku_name")))
        got = cur.fetchone()
        if got:
            cur.execute("UPDATE order_item SET sku_price=%s, sku_num=%s, platform_type=%s, "
                        "update_time=NOW() WHERE id=%s",
                        (item.get("sku_price"), item.get("sku_num"),
                         item.get("platform_type"), got[0]))
            return got[0]
        cur.execute("INSERT INTO order_item (order_id, sku_name, sku_price, sku_num, platform_type, "
                    "create_time, update_time) VALUES (%s,%s,%s,%s,%s,NOW(),NOW())",
                    (order_id, item.get("sku_name"), item.get("sku_price"),
                     item.get("sku_num"), item.get("platform_type")))
        return cur.lastrowid


def upsert_source_relation(conn, row):
    """按 uk_platform_order_source(platform_type, order_no, source_order_no) upsert。"""
    if not row.get("source_order_no"):
        return 0
    cols = ["order_no", "source_order_no", "platform_type", "platform_product_id",
            "platform_product_code", "platform_product_title", "platform_selling_price",
            "platform_freight", "source_product_id", "source_product_code",
            "source_product_title", "source_selling_price", "source_freight",
            "order_status", "order_time", "remark"]
    ph = ",".join(["%s"] * len(cols))
    upd = ",".join(f"{c}=VALUES({c})" for c in cols
                   if c not in ("order_no", "source_order_no", "platform_type"))
    sql = (f"INSERT INTO order_source_relation ({','.join(cols)}) VALUES ({ph}) "
           f"ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])
    return 1


def upsert_promo_account_daily(conn, row):
    """按 uk_promo_daily(shop_id, plan_type, campaign_id, stat_date) upsert。"""
    cols = ["shop_id", "platform_code", "stat_date", "plan_type", "campaign_id",
            "campaign_name", "report_source", "charge"]
    ph = ",".join(["%s"] * len(cols))
    upd = ",".join(f"{c}=VALUES({c})" for c in ("campaign_name", "charge"))
    sql = (f"INSERT INTO promo_cost_daily ({','.join(cols)}) VALUES ({ph}) "
           f"ON DUPLICATE KEY UPDATE {upd}")
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])
    return 1
```

> 注：`parse_isv_row` 的 `taobao_price` 正则较脆（ISV 行里同时有淘宝售价 `¥` 与采购金额 `￥（含运费）`）。Task 3 的 dry-run 会打印原始行，实现者据实修正该正则并同步补一条断言。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation && venv/bin/python tb-auto/test_pnl_common.py`
Expected: `test_pnl_common: ALL PASS`

- [ ] **Step 5: 提交（仅当用户明确要求时）**

```bash
git add automation/tb-auto/pnl_common.py automation/tb-auto/test_pnl_common.py
git commit -m "feat(pnl): shared parse/map/upsert helpers for pnl collectors"
```

---

### Task 2: 淘宝订单采集器 `collect_taobao_trade.py`

**Files:**
- Create: `automation/tb-auto/collect_taobao_trade.py`
- Test: 无单测（DOM 相关），靠 `--dry-run --limit` 目视 + DB SQL 抽查

**Interfaces:**
- Consumes: Task 1 的 `parse_sold_cells`、`build_order_info_row`、`build_order_item_row`、`upsert_order_info`、`upsert_order_item`、`quarter_windows`、`connect_db`、`log`；`cdp_utils.connect_cdp`；`shop_ref.default_shop_id`。
- Produces: 命令行 `collect_taobao_trade.py --dry-run --limit N --from YYYY-MM-DD --to YYYY-MM-DD --split YYYY-MM-DD`；进度文件 `taobao_trade_progress.json`。

**已实地验证的选择器（照抄）：**
- 页面 `https://myseller.taobao.com/home.htm/trade-platform/tp/sold`
- 切「3个月前」：`[...document.querySelectorAll('li')].find(x=>(x.innerText||'').trim()==='3个月前').click()`
- 设区间：点 `input[placeholder="起始日期"]` → `.next-range-picker-panel-input-start-date input` / `.next-range-picker-panel-input-end-date input` → `fill` → `Enter` → `Escape`
- 搜索：`button` 文本「搜索订单」，取最后一个（`btns.nth(n-1)`）
- 行数/条数：`document.body.innerText.match(/共\s*([\d,]+)\s*条/)`

- [ ] **Step 1: 写 `collect_taobao_trade.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集淘宝「已卖出宝贝」订单 → order_info + order_item (platform_type=1)。

只读: 只翻页/打字设条件, 绝不点任何写按钮。
跑法:
  automation/venv/bin/python tb-auto/collect_taobao_trade.py --dry-run --limit 5
  automation/venv/bin/python tb-auto/collect_taobao_trade.py --from 2024-10-01 --to 2026-07-14
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import (build_order_info_row, build_order_item_row, connect_db,  # noqa: E402
                        log, parse_sold_cells, quarter_windows, upsert_order_info,
                        upsert_order_item)

PORT = 9222
SOLD = "https://myseller.taobao.com/home.htm/trade-platform/tp/sold"
PROGRESS = os.path.join(BASE, "taobao_trade_progress.json")

EXTRACT_JS = r"""() => {
  const trs=[...document.querySelectorAll('table tbody tr')].filter(tr=>(tr.innerText||'').trim());
  return trs.map(tr=>({
    cells:[...tr.querySelectorAll('td')].map(td=>(td.innerText||'').trim()),
    raw:(tr.innerText||'').replace(/\n+/g,' / ')
  }));
}"""


def read_progress():
    if os.path.exists(PROGRESS):
        with open(PROGRESS, encoding="utf-8") as f:
            return json.load(f)
    return {"done_windows": [], "near_done": False}


def save_progress(pg):
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(pg, f, ensure_ascii=False, indent=2)


async def dismiss_overlays(p):
    for _ in range(3):
        if not await p.evaluate("() => !!document.querySelector('.next-overlay-wrapper.opened')"):
            return
        await p.keyboard.press("Escape")
        await p.wait_for_timeout(400)


async def set_range(p, start, end):
    await dismiss_overlays(p)
    await p.locator('input[placeholder="起始日期"]').first.click()
    await p.wait_for_timeout(1200)
    s = p.locator('.next-range-picker-panel-input-start-date input')
    await s.click(); await s.fill(start); await p.wait_for_timeout(400)
    e = p.locator('.next-range-picker-panel-input-end-date input')
    await e.click(); await e.fill(end); await p.wait_for_timeout(400)
    await p.keyboard.press("Enter"); await p.wait_for_timeout(1000)
    await dismiss_overlays(p)
    btns = p.locator('button', has_text="搜索订单")
    await btns.nth(await btns.count() - 1).click()
    await p.wait_for_timeout(5000)


async def next_page(p):
    for sel in ('button:has-text("下一页")', '.next-pagination-next button'):
        loc = p.locator(sel).first
        if await loc.count():
            disabled = await loc.evaluate("e => e.disabled || e.className.includes('disabled')")
            if disabled:
                return False
            await loc.click()
            await p.wait_for_timeout(4000)
            return True
    return False


def parse_page(rows):
    out = []
    for r in rows:
        parsed = parse_sold_cells(r.get("cells") or [])
        if parsed:
            parsed["_raw"] = r.get("raw")
            out.append(parsed)
    return out


async def collect_segment(p, conn, shop_id, tag, args, pg):
    """翻完当前视图所有页, 落库。rows_total 计数返回 (rows, pages)。"""
    page = 1
    total = 0
    while page <= args.max_pages:
        rows = await p.evaluate(EXTRACT_JS)
        parsed = parse_page(rows)
        if not parsed:
            break
        if args.dry_run:
            for x in parsed[:2]:
                log(f"  [dry] {x['order_no']} {x['create_time']} ¥{x['real_pay']} "
                    f"{x['trade_status']} {x['after_sale_status']} | {x['title']}")
        else:
            n = 0
            for x in parsed:
                oid = upsert_order_info(conn, build_order_info_row(x, shop_id))
                upsert_order_item(conn, oid, build_order_item_row(x))
                n += 1
            conn.commit()
            total += n
        log(f"{tag} 第{page}页: {len(parsed)} 行")
        if args.limit and total >= args.limit:
            break
        if not await next_page(p):
            break
        page += 1
    return total


async def run(args):
    hist_end = args.hist_end or args.split
    windows = quarter_windows(args.dfrom, hist_end)
    if not windows:
        log(f"历史窗口为空: {args.dfrom} ~ {hist_end}")
    b, ctx = await connect_cdp(PORT, keep_urls=["myseller.taobao.com", "taobao.com", "ufuwu.1688.com"], log=log)
    conn = None if args.dry_run else connect_db()
    pg = read_progress()
    try:
        p = await ctx.new_page()
        cur = None
        if not args.dry_run:
            with conn.cursor() as c:
                from shop_ref import default_shop_id, PLATFORM_TAOBAO
                cur = default_shop_id(c, PLATFORM_TAOBAO)
        try:
            await p.goto(SOLD, wait_until="domcontentloaded", timeout=60000)
            await p.wait_for_timeout(9000)
            await p.evaluate("() => { const e=[...document.querySelectorAll('li')]"
                             ".find(x=>(x.innerText||'').trim()==='3个月前'); if(e)e.click(); }")
            await p.wait_for_timeout(6000)
            for start, end in windows:
                key = f"{start}~{end}"
                if key in pg["done_windows"] and not args.force:
                    log(f"跳过已完成窗口 {key}")
                    continue
                await set_range(p, start, end)
                n = await collect_segment(p, conn, cur, f"历史 {key}", args, pg)
                if not args.dry_run:
                    pg["done_windows"].append(key); save_progress(pg)
            if not pg.get("near_done") or args.force:
                await p.evaluate("() => { const e=[...document.querySelectorAll('li')]"
                                 ".find(x=>(x.innerText||'').trim()==='近3个月'); if(e)e.click(); }")
                await p.wait_for_timeout(6000)
                await collect_segment(p, conn, cur, "近3个月", args, pg)
                if not args.dry_run:
                    pg["near_done"] = True; save_progress(pg)
        finally:
            await p.close()
    finally:
        if conn:
            conn.close()
        await b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--to", dest="dto", default=date.today().isoformat())
    ap.add_argument("--split", dest="split",
                    default=(date.today() - timedelta(days=90)).isoformat(),
                    help="历史/近期视图分界日")
    ap.add_argument("--hist-end", default=None, help="历史段截止(默认=split)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="忽略进度重跑")
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: dry-run 单窗口目视校验**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation && venv/bin/python tb-auto/collect_taobao_trade.py --dry-run --from 2024-10-01 --to 2024-12-31 --hist-end 2024-12-31 --limit 5`
Expected: 打印 5 行 `[dry] 订单号 时间 ¥金额 交易状态 售后状态 | 标题`，字段无错位（订单号 15-20 位、金额与页面一致、状态是中文）。若错位，先改 `parse_sold_cells` 的单元格下标并补 `test_pnl_common.py` 断言。

- [ ] **Step 3: 真实落库一个窗口**

Run: `venv/bin/python tb-auto/collect_taobao_trade.py --from 2024-10-01 --to 2024-12-31 --hist-end 2024-12-31`
Expected: 日志逐页 `历史 2024-10-01~2024-12-31 第N页: M 行`，进度文件写 `done_windows`。

- [ ] **Step 4: SQL 抽查**

Run:
```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e \
"SELECT COUNT(*) FROM order_info WHERE platform_type=1 AND create_time>='2024-10-01' AND create_time<'2025-01-01'; \
 SELECT COUNT(*) FROM order_item i JOIN order_info o ON o.id=i.order_id WHERE o.platform_type=1 AND o.create_time>='2024-10-01';"
```
Expected: 两数均 > 0；`order_item` 数 ≥ `order_info` 数。

- [ ] **Step 5: 全量跑**（可断点续跑，中断后重跑跳过 `done_windows`）

Run: `venv/bin/python tb-auto/collect_taobao_trade.py`
Expected: 8 个历史窗口 + 近期段全部走完；`taobao_trade_progress.json` 里 `done_windows` 8 项、`near_done=true`。

- [ ] **Step 6: 提交（仅当用户明确要求时）**

```bash
git add automation/tb-auto/collect_taobao_trade.py
git commit -m "feat(pnl): collect taobao sold orders into order_info/order_item"
```

---

### Task 3: 1688 代发单采集器 `collect_1688_agency_order.py`

**Files:**
- Create: `automation/tb-auto/collect_1688_agency_order.py`
- Test: 无单测（DOM 相关），靠 `--dry-run` 打印原始行 + DB SQL 抽查

**Interfaces:**
- Consumes: Task 1 的 `parse_isv_row`、`build_source_relation_row`、`upsert_source_relation`、`connect_db`、`log`；`cdp_utils.connect_cdp`。
- Produces: 命令行 `collect_1688_agency_order.py --dry-run --max-pages N`；进度文件 `isv_order_progress.json`。

**已实地验证的选择器（照抄）：**
- 入口 `https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818`；业务 iframe URL 含 `isv-container`。
- 切列表：`container.evaluate("() => { location.hash = '#/order/list'; }")`
- 关密文提示：点文本 `确 定`/`确定` 的 button
- 点「全部」tab：`[...document.querySelectorAll('*')].find(e=>/^全部\s*\(\d+\)$/.test((e.innerText||'').trim())&&e.children.length<=1).click()`
- 查询：`[...document.querySelectorAll('button')].find(b=>/查\s*询/.test(b.innerText||''))`
- 行：`.ant-table-row`；行内店铺订单号 `a[title="店铺订单号"]`；1688 商品ID `span.order-id`
- 分页：`.ant-pagination-next`（`.ant-pagination-disabled` 时到底）；总条数 `document.body.innerText.match(/共(\d+)条/)`

- [ ] **Step 1: 写 `collect_1688_agency_order.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 1688 ISV 分销工作台「全部」代发单 → order_source_relation。

只读: 只点「全部」tab / 查询 / 翻页, 绝不点 采购/打单/发货/关闭/忽略。
断点续跑: isv_order_progress.json 记已翻页的日期区间(按末行时间), 简化处理 = 整段重拉幂等 upsert。
跑法:
  automation/venv/bin/python tb-auto/collect_1688_agency_order.py --dry-run
  automation/venv/bin/python tb-auto/collect_1688_agency_order.py
"""
import argparse
import asyncio
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from cdp_utils import connect_cdp  # noqa: E402
from pnl_common import (build_source_relation_row, connect_db, log, parse_isv_row,  # noqa: E402
                        upsert_source_relation)

PORT = 9222
URL = "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"
PROGRESS = os.path.join(BASE, "isv_order_progress.json")

EXTRACT_JS = r"""() => {
  const trs=[...document.querySelectorAll('.ant-table-row')].filter(t=>(t.innerText||'').trim());
  return trs.map(tr=>{
    const a=tr.querySelector('a[title="店铺订单号"]');
    const idEl=tr.querySelector('span.order-id');
    const ot=(a?a.innerText:'').trim();
    const href=a?a.getAttribute('href')||'':'';
    const m=href.match(/biz_order_id=(\d+)/);
    return {
      shop_order_no: (m?m[1]:ot)||'',
      source_product_id: idEl?(idEl.innerText||'').replace(/\D/g,''):'',
      raw:(tr.innerText||'').replace(/\n+/g,' / ')
    };
  });
}"""


async def open_order_list(p):
    await p.goto(URL, wait_until="domcontentloaded", timeout=60000)
    await p.wait_for_timeout(12000)
    frame = next((f for f in p.frames if "isv-container" in f.url), None)
    if frame is None:
        raise RuntimeError("找不到 isv-container iframe(登录态掉了?)")
    await frame.evaluate("() => { location.hash = '#/order/list'; }")
    await p.wait_for_timeout(7000)
    return next((f for f in p.frames if "isv-container" in f.url), frame)


async def close_secret_modal(frame):
    await frame.evaluate("""() => { [...document.querySelectorAll('button')]
      .forEach(b=>{ if(/^确\s*定$/.test((b.innerText||'').trim())) b.click(); }); }""")
    await frame.wait_for_timeout(1200)


async def pick_all_tab(frame):
    await frame.evaluate("""() => { const t=[...document.querySelectorAll('*')]
      .find(e=>/^全部\\s*\\(\\d+\\)$/.test((e.innerText||'').trim())&&e.children.length<=1); if(t)t.click(); }""")
    await frame.wait_for_timeout(2500)


async def query(frame):
    ok = await frame.evaluate("""() => { const b=[...document.querySelectorAll('button')]
      .find(b=>/查\\s*询/.test(b.innerText||'')); if(b){b.click();return true;} return false; }""")
    await frame.wait_for_timeout(7000)
    return ok


async def next_page(frame):
    return await frame.evaluate("""() => { const b=document.querySelector('.ant-pagination-next');
      if(!b || b.classList.contains('ant-pagination-disabled')) return false; b.click(); return true; }""")


async def run(args):
    b, ctx = await connect_cdp(PORT, keep_urls=["ufuwu.1688.com", "myseller.taobao.com", "taobao.com"], log=log)
    conn = None if args.dry_run else connect_db()
    stats = {"rows": 0, "written": 0, "no_source_no": 0}
    try:
        p = await ctx.new_page()
        try:
            frame = await open_order_list(p)
            await close_secret_modal(frame)
            await pick_all_tab(frame)
            await query(frame)
            total = await frame.evaluate(r"""() => { const m=document.body.innerText.match(/共(\d+)条/); return m?parseInt(m[1]):-1; }""")
            log(f"ISV 全部 共 {total} 条")
            for page in range(1, args.max_pages + 1):
                rows = await frame.evaluate(EXTRACT_JS)
                if not rows:
                    break
                for r in rows:
                    stats["rows"] += 1
                    isv = parse_isv_row(r["shop_order_no"], r["source_product_id"], None, r["raw"])
                    row = build_source_relation_row(isv)
                    if not row.get("source_order_no"):
                        stats["no_source_no"] += 1
                        if args.dry_run:
                            log(f"  [no采购单号] {r['shop_order_no']} :: {r['raw'][:120]}")
                        continue
                    if args.dry_run:
                        log(f"  [dry] {row['order_no']} <- 1688:{row['source_order_no']} "
                            f"¥{row['source_selling_price']} {row['order_status']} {row['order_time']}")
                    else:
                        stats["written"] += upsert_source_relation(conn, row)
                if not args.dry_run:
                    conn.commit()
                log(f"第{page}页: {len(rows)} 行")
                if not await next_page(frame):
                    break
                await p.wait_for_timeout(3500)
        finally:
            await p.close()
    finally:
        if conn:
            conn.close()
        await b.close()
    log(f"完成: 扫到 {stats['rows']} 行, 写入 {stats['written']}, 无采购单号 {stats['no_source_no']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-pages", type=int, default=80)
    sys.exit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: dry-run 打印原始行，确认 1688 采购单号位置**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation && venv/bin/python tb-auto/collect_1688_agency_order.py --dry-run --max-pages 3`
Expected: 若大量 `[no采购单号]`，说明 `采购单号` 不在 `raw` 文本里 —— 用打印出的原始行定位采购单号（可能在行内其它 span / 「采购日志」查看器），修正 `parse_isv_row` 的正则并补 `test_pnl_common.py` 断言；若行内确实没有，改为从行内 `.order-id` 旁的另一个元素取。直到 dry-run 能稳定打印 `1688:xxx`。

- [ ] **Step 3: 真实落库**

Run: `venv/bin/python tb-auto/collect_1688_agency_order.py`
Expected: 逐页 `第N页: 20 行`，末尾 `扫到 ~202 行, 写入 ~202`。

- [ ] **Step 4: SQL 抽查**

Run:
```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e \
"SELECT COUNT(*) FROM order_source_relation WHERE platform_type=1 AND source_order_no IS NOT NULL; \
 SELECT order_no, source_order_no, source_selling_price, source_freight, order_status, order_time FROM order_source_relation ORDER BY id DESC LIMIT 5;"
```
Expected: 计数与 ISV `共 N 条` 吻合（允许 ±幂等去重），采购金额/运费/状态/下单时间非空。

- [ ] **Step 5: 提交（仅当用户明确要求时）**

```bash
git add automation/tb-auto/collect_1688_agency_order.py
git commit -m "feat(pnl): collect 1688 ISV agency orders into order_source_relation"
```

---

### Task 4: 阿里妈妈账户每日 `collect_alimama_account_daily.py`

**Files:**
- Create: `automation/tb-auto/collect_alimama_account_daily.py`

**Interfaces:**
- Consumes: `collect_alimama_promo.py` 的 `borrow_template`、`connect_db`、`date_range`、`BIZ`、`PORT`、`hit_risk`（只读复用）；`pnl_common.upsert_promo_account_daily`、`log`；`shop_ref.default_shop_id`。
- Produces: 命令行 `collect_alimama_account_daily.py --from --to --days --dry-run`。

**口径（写在文件头注释）：** 账户每日花费 = 两个投放产品（`onebpSearch` 关键词 + `onebpDisplay` 人群）当日全部计划 `charge` 之和。假设该账户只跑这两个产品；若后续发现其它产品，在此文件汇总处补一个 `BIZ` 项。

- [ ] **Step 1: 写 `collect_alimama_account_daily.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阿里妈妈账户每日花费 → promo_cost_daily(report_source='account', plan_type='account')。

只读: 复用 collect_alimama_promo 的只读 findPage 查询方式, 不点任何写按钮。
口径: 账户每日 charge = onebpSearch + onebpDisplay 当日全部计划 charge 之和(见模块注释)。
跑法:
  automation/venv/bin/python tb-auto/collect_alimama_account_daily.py --days 15 --dry-run
  automation/venv/bin/python tb-auto/collect_alimama_account_daily.py --from 2024-10-01 --to 2026-09-30
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


async def sum_day(page, tpl, biz_code, day):
    """借页面上下文发一次 findPage(翻页汇总 charge), 返回当日 charge 合计。"""
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
            tpls = {}
            for biz_code, _ in BIZ:
                tpls[biz_code] = await borrow_template(page, biz_code, days[-1])
                if not tpls[biz_code]:
                    log(f"!! {biz_code} 没借到 findPage 参数(登录态掉了?)")
                    return 1
            written = 0
            for day in days:
                charge = 0.0
                for biz_code, _ in BIZ:
                    charge += await sum_day(page, tpls[biz_code], biz_code, day)
                row = {"shop_id": shop_id, "platform_code": 1, "stat_date": day,
                       "plan_type": "account", "campaign_id": "account",
                       "campaign_name": None, "report_source": "account",
                       "charge": round(charge, 2)}
                if args.dry_run:
                    log(f"  [dry] {day} 账户花费 = {row['charge']}")
                else:
                    written += upsert_promo_account_daily(conn, row)
                    conn.commit()
                await asyncio.sleep(1.5)
            log(f"完成: {len(days)} 天, 写入 {written}")
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
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.days:
        a.dfrom = (datetime.strptime(a.dto, "%Y-%m-%d").date() - timedelta(days=a.days - 1)).isoformat()
    if not a.dfrom:
        a.dfrom = (datetime.strptime(a.dto, "%Y-%m-%d").date() - timedelta(days=14)).isoformat()
    sys.exit(asyncio.run(run(a)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: dry-run 校验**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation && venv/bin/python tb-auto/collect_alimama_account_daily.py --days 5 --dry-run`
Expected: 打印 5 天 `账户花费 = x.xx`；与万相台账户报表当日花费目视一致。

- [ ] **Step 3: 分段落库 24 个月**

Run: `venv/bin/python tb-auto/collect_alimama_account_daily.py --from 2024-10-01 --to 2025-03-31`，再逐段跑到 `2026-09-30`（`date_range` 上限 90 天，分 8 段）。
Expected: 每段末 `完成: N 天, 写入 N`。

- [ ] **Step 4: SQL 抽查**

Run:
```bash
/usr/local/mysql/bin/mysql --defaults-extra-file=/tmp/spzx_my.cnf db_spzx -e \
"SELECT MIN(stat_date), MAX(stat_date), COUNT(*), SUM(charge) FROM promo_cost_daily WHERE report_source='account' AND platform_code=1;"
```
Expected: 日期覆盖 2024-10 ~ 2026-09；`COUNT(*)` ≈ 24 个月天数；`SUM(charge) > 0`。

- [ ] **Step 5: 提交（仅当用户明确要求时）**

```bash
git add automation/tb-auto/collect_alimama_account_daily.py
git commit -m "feat(pnl): collect alimama account daily spend into promo_cost_daily"
```

---

### Task 5: 刷单候选清单 `detect_brush_orders.py`

**Files:**
- Create: `automation/tb-auto/detect_brush_orders.py`

**Interfaces:**
- Consumes: Task 1 的 `brush_candidates`、`connect_db`、`log`。
- Produces: 命令行 `detect_brush_orders.py --from --to --out`；输出 JSONL + 控制台摘要。**不写 `brush_order`。**

- [ ] **Step 1: 写 `detect_brush_orders.py`**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷单候选: 淘宝订单 ∈ order_info(platform_type=1) 但 ∉ order_source_relation.order_no。

纯 DB 只读, 不写 brush_order(阶段一只出清单)。
跑法: automation/venv/bin/python tb-auto/detect_brush_orders.py --from 2024-10-01 --to 2026-09-30
"""
import argparse
import json
import os
import sys
from decimal import Decimal

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "sourcing"))
from pnl_common import brush_candidates, connect_db, log  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2024-10-01")
    ap.add_argument("--to", dest="dto", default="2026-09-30")
    ap.add_argument("--out", default=os.path.join(BASE, "brush_candidates.jsonl"))
    a = ap.parse_args()
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT o.order_no, o.create_time, o.total_amount, o.order_status, o.remark "
                "FROM order_info o WHERE o.platform_type=1 AND o.is_deleted=0 "
                "AND o.create_time >= %s AND o.create_time < DATE_ADD(%s, INTERVAL 1 DAY)",
                (a.dfrom, a.dto))
            orders = [{"order_no": r[0], "create_time": str(r[1]), "total_amount": r[2],
                       "order_status": r[3], "remark": r[4]} for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT order_no FROM order_source_relation WHERE platform_type=1")
            related = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    cand = brush_candidates(orders, related)
    with open(a.out, "w", encoding="utf-8") as f:
        for c in cand:
            amt = c["total_amount"]
            f.write(json.dumps({**c, "total_amount": str(amt) if isinstance(amt, Decimal) else amt},
                               ensure_ascii=False) + "\n")
    amt_sum = sum((c["total_amount"] or Decimal("0")) for c in cand)
    log(f"淘宝订单 {len(orders)}, 有 1688 关联 {len(related)}, 刷单候选 {len(cand)} "
        f"(候选金额合计 {amt_sum})")
    log(f"清单: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 运行并核对**

Run: `cd /Users/qyk9527/ideaProject/spzx-parent/automation && venv/bin/python tb-auto/detect_brush_orders.py`
Expected: 控制台一行摘要 + 生成 `brush_candidates.jsonl`。与 `brush_order` 现有手工记录比对：手工记录应大体落在候选清单里（不要求完全一致，口径确认后再定是否写库）。

- [ ] **Step 3: 提交（仅当用户明确要求时）**

```bash
git add automation/tb-auto/detect_brush_orders.py
git commit -m "feat(pnl): output brush-order candidate list (read-only)"
```

---

## Self-Review

**Spec 覆盖：**
- §2.1 淘宝订单 → Task 2（两视图、Fusion 区间、搜索按钮、8-td 解析）
- §2.2 1688 ISV → Task 3（全部 tab、翻页、密文弹窗、行解析）
- §2.3 阿里妈妈账户每日 → Task 4
- §3 落库映射 → Task 1 的 `build_*_row` + `upsert_*`（表名/列名对照 schema 逐一核过）
- §4 关联与刷单 → Task 1 `brush_candidates` + Task 5
- §5 采集器形态（只读/断点/CLI）→ 各 Task 的 CLI 与进度文件
- §6 验证 → 各 Task 的 dry-run + SQL 抽查
- §7 未决项 → Task 3 的采购单号定位步骤、Task 2 的单元格下标校验步骤、Task 4 的产品口径注释

**Placeholder 扫描：** 无 TBD/TODO；每个代码步骤都给了可运行代码。唯一"待实地确认"处（ISV 采购单号正则、淘宝 td 下标）已写成明确的 dry-run 校验 + 修正步骤，而非占位符。

**类型一致性：** 后续三个 collector 引用的函数名/字段名与 Task 1 定义逐一对应：`parse_sold_cells`/`build_order_info_row`/`build_order_item_row`/`upsert_order_info`（返回 `order_info.id`）/`upsert_order_item`；`parse_isv_row`→`build_source_relation_row`→`upsert_source_relation`；`upsert_promo_account_daily`；`brush_candidates`。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-12-pnl-collector.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 Task 派一个全新子代理，任务间我来 review，迭代快。

**2. Inline Execution** — 在本会话按 executing-plans 批量执行，带检查点。

Which approach?
