#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pnl_common 纯函数自检. 跑法: automation/venv/bin/python tb-auto/test_pnl_common.py"""
from decimal import Decimal
from pnl_common import (brush_candidates, build_order_info_row, build_order_item_row,
                        build_source_relation_row, map_purch_status, map_trade_status,
                        parse_dt, parse_int, parse_isv_row, parse_money,
                        parse_sold_cells, quarter_windows)
# 生产行适配器(未被 parse_sold_cells 覆盖的、易漂移的一段): 头行+商品行 → 单行 8 列。
# 只导入纯函数; collect_taobao_trade 顶层仅定义常量/函数 + __main__ 守卫, 不启动浏览器。
from collect_taobao_trade import parse_page

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
assert map_trade_status("买家已付款") == 1
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

# ---- 生产端→消费端全链路: parse_isv_row → build_source_relation_row ----
# 回归: parse_isv_row 必须回**原始状态字符串**, 映射只由 build_source_relation_row 做一次。
_raw = ("订单号：3234787251801271563 / 2024-10-05 13:00:00 / ID：810276543210 / "
        "¥69.90 / 采购金额 ￥32.50（含运费￥0.00） / 采购单号：5060020214474601936 / 已成功")
_p = parse_isv_row("3234787251801271563", "810276543210", None, _raw)
assert _p["purch_status"] == "已成功"                 # 原始关键词, 不是 int
assert _p["purch_amount"] == Decimal("32.50")
assert _p["taobao_price"] == Decimal("69.90")
assert _p["source_freight"] == Decimal("0.00")
_sr = build_source_relation_row(_p)
assert _sr["order_status"] == 3 and _sr["source_order_no"] == "5060020214474601936"

# ---- 真实 ISV 行格式: 采购单号标签与号码间有 \n->" / " 归一化分隔符 ----
# 实测 raw(innerText.replace(\n+," / ")) 片段: "采购单号： / 5127345723001028719 / 赚第一桶钱"
_raw_live = ("茎肛葫芦娃q / 5127850117001001603 / 2026-10-12 13:59:38 / 采购日志 / 预览 / "
             "超短裤性感欲纯女生夏季2026新超短裤辣妹装不规则破洞牛仔裤 / ¥35.10 / ID： / "
             "1058428800598 / 颜色分类:浅蓝色【高品质】 / 尺寸:XL / x1 / 亏 / 已发货 / "
             "￥30.80 / （含运费￥0.00） / 采购单号： / "
             "5127345723001028719 / 查看物流 / 密文下单")
_pl = parse_isv_row("5127850117001001603", "920682245695", None, _raw_live)
assert _pl["source_order_no"] == "5127345723001028719", _pl["source_order_no"]
assert _pl["purch_amount"] == Decimal("30.80")      # 紧跟（含运费 的才判为货款
assert _pl["taobao_price"] == Decimal("35.10")
assert _pl["source_freight"] == Decimal("0.00")

# 退款/关闭且从未采购的行 genuinely 没有采购单号 -> 保持 None (写入器跳过并计数)
_raw_nopurch = ("茎肛葫芦娃q / 3316488567001005391 / 2026-10-10 17:59:02 / 采购日志 / 退款成功 / "
                "预览 / 大码收腰派克服 / ¥199.00 / ID： / 760216419668 / 已关闭 / ￥147.00 / "
                "（含运费￥0.00）")
assert parse_isv_row("3316488567001005391", "742890863978", None, _raw_nopurch)["source_order_no"] is None

# ---- 生产行适配器 parse_page: 真实布局 头行(1 td) + 商品行(7 td) ----
# 已卖出宝贝每单拆成两行; parse_page 把二者并成 parse_sold_cells 期望的 8 列,
# 并清洗商品行 3/4 列(履约/售后 与 交易状态)里混着的操作按钮文案。
def _prow(cells):
    return {"cells": cells, "raw": " / ".join(cells)}


_HEAD1 = "订单号：3234787251801271563\n2024-10-05 12:34:56\n买家：t**"
_PROD1 = ["秋冬加绒睡裙 粉色 M\n颜色分类：粉色；尺码：M\n商家编码：ABC123",
          "¥69.90", "x1", "退款成功\n申请退款", "交易成功 详情\n打单\n发货",
          "实收款￥69.90", "查看物流"]
_PROD2 = ["秋冬加绒睡裙 蓝色 L\n颜色分类：蓝色；尺码：L\n商家编码：DEF456",
          "¥59.90", "x2", "", "交易成功 详情\n打单", "实收款￥119.80", "查看物流"]
_HEAD2 = "订单号：3234787251801271999\n2024-10-06 08:00:00\n买家：a**"
_PROD3 = ["纯棉家居服 灰色 XL\n颜色分类：灰色；尺码：XL",
          "¥39.00", "x1", "", "交易关闭 详情\n删除订单", "实收款￥0.00", "查看物流"]

_pp = parse_page([_prow([_HEAD1]), _prow(_PROD1), _prow(_PROD2),
                  _prow([_HEAD2]), _prow(_PROD3)])
assert len(_pp) == 3, len(_pp)                    # 头行不产, 一单多商品各产一条
r1, r2, r3 = _pp
assert r1["order_no"] == "3234787251801271563"    # 列位: 头行 → 订单号
assert r1["create_time"] == "2024-10-05 12:34:56"
assert r1["unit_price"] == Decimal("69.90")       # 商品行第 1 列 → 单价
assert r1["qty"] == 1                             # 第 2 列 → 数量
assert r1["after_sale_status"] == "退款成功"       # 第 3 列, 只留首行真状态
assert r1["trade_status"] == "交易成功"            # 第 4 列, 去「详情」+ 按钮文案
assert r1["real_pay"] == Decimal("69.90")         # 第 5 列 → 实收款
# 同单第二件: 复用同一头行, order_no 相同、sku/金额各自独立
assert r2["order_no"] == r1["order_no"]
assert r2["sku_name"] != r1["sku_name"]
assert r2["unit_price"] == Decimal("59.90") and r2["qty"] == 2
assert r2["after_sale_status"] is None            # 空单元格 → None, 不塌成 ""
assert r2["real_pay"] == Decimal("119.80")
# 新头行 → 新订单号(头行状态会被重置)
assert r3["order_no"] == "3234787251801271999"
assert r3["trade_status"] == "交易关闭" and r3["real_pay"] == Decimal("0.00")
assert all("_raw" in x for x in _pp)              # 原始 innerText 透传给下游

# ---- 刷单判定：有淘宝单、无 1688 关联 ----
orders = [{"order_no": "A", "create_time": "2024-10-05 12:00:00",
           "total_amount": Decimal("69.90"), "trade_status": "交易成功"},
          {"order_no": "B", "create_time": "2024-10-06 12:00:00",
           "total_amount": Decimal("59.00"), "trade_status": "交易成功"}]
cand = brush_candidates(orders, {"A"})
assert [c["order_no"] for c in cand] == ["B"]

print("test_pnl_common: ALL PASS")
