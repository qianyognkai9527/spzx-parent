#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成交侧字段 + 覆盖率判定的纯函数测试（不连库、不开浏览器）。

跑法: automation/venv/bin/python automation/sourcing/test_sycm_money_fields.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cron_batch import COVERAGE_RATIO, coverage_verdict  # noqa: E402
from sycm_item_snapshot import _opt_num, parse_items  # noqa: E402
from backfill_sycm_money_fields import extract  # noqa: E402

import json

checks = 0


def eq(actual, expected, msg):
    global checks
    assert actual == expected, f"{msg}: 期望 {expected!r} 实得 {actual!r}"
    checks += 1


def ok(cond, msg):
    global checks
    assert cond, msg
    checks += 1


# ── _opt_num：没给 ≠ 给了 0 ──────────────────────────────────────────────
eq(_opt_num({"payAmt": {"value": 0}}, "payAmt"), 0.0, "值为 0 要留 0，不能变 NULL")
eq(_opt_num({}, "payAmt"), None, "键不存在 = 没采到")
eq(_opt_num({"payAmt": {"value": None}}, "payAmt"), None, "值为 null = 没采到")
eq(_opt_num({"payAmt": {"value": ""}}, "payAmt"), None, "空串 = 没采到")
eq(_opt_num({"payAmt": {"value": "99.46"}}, "payAmt"), 99.46, "字符串数字要能转")
eq(_opt_num({"payItmCnt": {"value": 3.0}}, "payItmCnt", True), 3, "件数取整")
eq(_opt_num({"payAmt": {"value": "–"}}, "payAmt"), None, "千分位破折号当没采到")
eq(_opt_num({"payAmt": 12.5}, "payAmt"), 12.5, "非嵌套形状也认")

# ── parse_items：四个成交字段进得了行 ─────────────────────────────────────
row = parse_items([{
    "itemId": {"value": "760216419668"},
    "itmUv": {"value": 10}, "itmPv": {"value": 14},
    "payByrCnt": {"value": 1}, "payAmt": {"value": 147.0},
    "payItmCnt": {"value": 2}, "crtAmt": {"value": 147.0},
    "crtItmQty": {"value": 2}, "sucRefundAmt": {"value": 0.0},
}], "recent7", "2026-09-08|2026-09-14")[0]
eq(row["pay_items"], 2, "pay_items ← payItmCnt")
eq(row["order_amt"], 147.0, "order_amt ← crtAmt")
eq(row["order_items"], 2, "order_items ← crtItmQty")
eq(row["refund_amt"], 0.0, "refund_amt ← sucRefundAmt（真 0，不是 NULL）")
eq(row["pay_amt"], 147.0, "原有 pay_amt 不受影响")

# 老结构（接口没这些键）必须留 NULL，否则历史回填会把"没采"写成"零成交"
old = parse_items([{"itemId": {"value": "1"}, "payAmt": {"value": 0}}],
                  "recent7", "r")[0]
eq((old["pay_items"], old["order_amt"], old["order_items"], old["refund_amt"]),
   (None, None, None, None), "缺键时四列全 NULL")

# ── extract：从库里存的 extra_json 反解 ─────────────────────────────────
eq(extract(json.dumps({"payItmCnt": {"value": 1}, "crtAmt": {"value": 99.0},
                        "crtItmQty": {"value": 1},
                        "sucRefundAmt": {"value": 99.46}})),
   (1, 99.0, 1, 99.46), "正常 JSON 四列")
eq(extract(None), None, "extra_json 为空要跳过而不是写 NULL 覆盖")
eq(extract('{"payItmCnt": {"val'), None, "截断的 JSON 要跳过")
eq(extract("[1,2]"), None, "非 dict 的 JSON 要跳过")

# ── coverage_verdict：只看退出码看不出来的那类事故 ────────────────────────
call, _ = coverage_verdict(100, None)
eq(call, "unknown", "没有基线时判 unknown，不假称正常")
call, _ = coverage_verdict(100, 286)
eq(call, "partial", "100 vs 286（2026-10-02 实测那轮）必须判 partial")
call, _ = coverage_verdict(283, 195)
eq(call, "ok", "283 vs 195 正常")
call, _ = coverage_verdict(0, 286)
eq(call, "partial", "0 条永远不算跑全")
call, detail = coverage_verdict(int(286 * COVERAGE_RATIO), 286)
eq(call, "partial", "286×0.6=171.6，171 条就是没到线")
ok("=172" in detail, f"文案里的阈值要写向上取整后的 172，实得 {detail}")
call, _ = coverage_verdict(172, 286)
eq(call, "ok", "172 条到达线")
call, _ = coverage_verdict(int(280 * COVERAGE_RATIO), 280)
eq(call, "ok", "整数线上（280×0.6=168）算达标")
call, _ = coverage_verdict(int(280 * COVERAGE_RATIO) - 1, 280)
eq(call, "partial", "差 1 条就判不足")

print(f"OK  {checks} 项断言全过")
