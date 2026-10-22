#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refund_common 纯函数自检. 跑法: automation/venv/bin/python tb-auto/test_refund_common.py"""
from decimal import Decimal

from refund_common import DERIVED_CODE, build_refund_row, map_import_order_status

assert DERIVED_CODE == "auto-refund"

# ---- 原始行(JS 抽出的字符串字段) → 落库行 ----
F = {
    "refund_no": "2000001234567890",
    "order_no": "3234787251801271563",
    "after_sale_type": "退货退款",
    "status": "退款成功",
    "refund_amount": "¥69.90",
    "order_amount": "99.00",
    "apply_time": "2024-10-06 10:00:00",
    "finish_time": "2024-10-08 12:00:00",
    "reason": "尺码不符",
    "product_title": "秋冬加绒睡裙 粉色 M",
    "sku_name": "颜色分类：粉色；尺码：M",
    "item_id": "1058428800598",
    "buyer_nick": "t**",
    "raw": "整行原始文本",
}
r = build_refund_row(F, shop_id=1)
assert r["refund_no"] == "2000001234567890"
assert r["order_no"] == "3234787251801271563"
assert r["after_sale_type"] == "退货退款"
assert r["platform_type"] == 1 and r["shop_id"] == 1
assert r["refund_amount"] == Decimal("69.90")
assert r["order_amount"] == Decimal("99.00")
assert r["apply_time"] == "2024-10-06 10:00:00"
assert r["finish_time"] == "2024-10-08 12:00:00"
assert r["item_id"] == "1058428800598"

# 缺退款编号 → None（调用方跳过）
assert build_refund_row({**F, "refund_no": ""}, 1) is None
# 金额脏值不崩，落 None
assert build_refund_row({**F, "refund_amount": "无"}, 1)["refund_amount"] is None

# ---- order_info.order_status(int) → refund_import_order.order_status(str) ----
assert map_import_order_status(-1) == "交易关闭"
assert map_import_order_status(3) == "交易成功"
assert map_import_order_status(1) == "买家已付款,等待卖家发货"
assert map_import_order_status(2) == "卖家已发货，等待买家确认"
assert map_import_order_status(0) == "等待买家付款"

print("test_refund_common: ALL PASS")
