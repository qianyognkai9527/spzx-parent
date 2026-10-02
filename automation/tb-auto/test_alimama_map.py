#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_alimama_promo 纯函数自检. 跑法: automation/venv/bin/python test_alimama_map.py

fixture 用的是 2026-10-03 实测抓到的真实一行(标准计划B / 2026-10-01), 不是编的:
charge=9.809999999999999 adPv=827 click=32 ctr=0.03869 ecpc=0.30656 ecpm=11.86215
"""
from collect_alimama_promo import (cast, date_range, hit_risk, is_standard, item_id_of,
                                   map_adgroup_row, map_row, should_page)

# ---- 类型转换: NULL 必须保持 NULL, 不能塌成 0 ----
assert cast(0.03869, "pct") == 3.869          # 比值 → 百分数
assert cast(0.0, "pct") == 0.0                # 报表给了 0 就是 0
assert cast(None, "pct") is None
assert cast("", "pct") is None
assert cast(827.0, "int") == 827
assert cast(9.809999999999999, "money") == 9.81
assert cast(0.30656, "rate") == 0.3066
assert cast("abc", "int") is None
assert cast(None, "money") is None

# ---- 真实一行 → 表行 ----
INFO = {"charge": 9.809999999999999, "adPv": 827.0, "click": 32.0, "ctr": 0.03869,
        "ecpc": 0.30656, "ecpm": 11.86215, "roi": 0.0, "cvr": 0.0,
        "alipayInshopAmt": 0.0, "alipayDirAmt": 0.0, "alipayInshopNum": 0.0,
        "alipayDirNum": 0.0, "cartInshopNum": 0.0, "cartRate": 0.0,
        "itemColInshopNum": 1.0, "shopColDirNum": 0.0, "colNum": 1.0,
        "colCartNum": 1.0, "itemColCart": 1.0, "colCartCost": 9.81,
        "itemColCartCost": 9.81, "itemColInshopCost": 9.81, "itemColInshopRate": 0.03125,
        "shoppingAmt": 0.0, "memberId": 114640889, "special_campaign_filter": 0}
camp = {"campaignId": 83392769388, "campaignName": "标准计划B", "bidType": "custom_bid",
        "onlineStatus": 1, "reportInfoList": [INFO]}
row, reason = map_row(camp, "2026-10-01", "keyword", 1, "batch-x")
assert reason is None and row is not None
assert row["campaign_id"] == "83392769388"
assert row["stat_date"] == "2026-10-01" and row["plan_type"] == "keyword"
assert row["charge"] == 9.81 and row["ad_pv"] == 827 and row["click"] == 32
assert row["ctr_percent"] == 3.869
assert row["cpc"] == 0.3066 and row["cpm"] == 11.8622
assert row["item_collect"] == 1 and row["collect_total"] == 1
assert row["item_collect_rate_percent"] == 3.125
assert row["bid_type"] == "custom_bid"
assert row["shop_id"] == 1 and row["platform_code"] == 1
# 接口没给的字段留 NULL(间接成交/间接购物车/新增客), 不是 0
assert row["order_indirect"] is None and row["cart_direct"] is None
assert row["add_new_uv"] is None
assert "83392769388" not in row["raw_json"] and "adPv" in row["raw_json"]

# ---- reportInfoList 为 null = 当天没有任何投放数据, 不是"花了 0 元" ----
paused = {"campaignId": 83392643008, "campaignName": "标准计划A", "bidType": "custom_bid",
          "reportInfoList": None}
r2, why = map_row(paused, "2026-10-01", "keyword", 1, "b")
assert r2 is None and why == "no_report"
assert map_row({"campaignId": 1, "reportInfoList": []}, "d", "keyword", 1, "b")[1] == "no_report"
assert map_row({"campaignName": "x", "reportInfoList": [INFO]}, "d", "keyword", 1, "b")[1] == "no_id"

# ---- shop_id 缺省 0(唯一键里的列不能 NULL) ----
assert map_row(camp, "2026-10-01", "keyword", None, "b")[0]["shop_id"] == 0

# ---- 标准计划判据 ----
assert is_standard("custom_bid") is True
assert is_standard("roi_control") is False
assert is_standard(None) is False
assert is_standard("roi_control", only_standard=False) is True

# ---- 日期区间 ----
assert date_range("2026-09-30", "2026-10-02") == ["2026-09-30", "2026-10-01", "2026-10-02"]
assert date_range("2026-10-02", "2026-10-02") == ["2026-10-02"]
assert date_range("2026-10-02", "2026-10-01") == []      # 起止反了
assert date_range("2026-01-01", "2026-10-01") == []      # 超 90 天
assert date_range("x", "2026-10-01") == []               # 格式错
assert date_range(None, "2026-10-01") == []

# ---- 风控识别 ----
assert hit_risk("页面提示 RGV587 请验证") == "RGV587"
assert hit_risk("FAIL_SYS_USER_VALIDATE") == "FAIL_SYS_USER_VALIDATE"
assert hit_risk('{"data":{"list":[]}}') is None
assert hit_risk(None) is None

# ---- 宝贝粒度: 单元就是宝贝, materialId 是 13 位淘宝商品ID ----
adg = {"adgroupId": 83708697345, "adgroupName": "性感收腰透视蕾丝吊带睡裙",
       "campaignId": 83392769388, "campaignName": "标准计划B", "onlineStatus": 1,
       "material": {"materialId": 1072639258886, "title": "性感收腰透视蕾丝吊带睡裙"},
       "reportInfoList": [dict(INFO)]}
irow, ireason = map_adgroup_row(adg, "2026-10-01", "keyword", 1, "src")
assert ireason is None and irow is not None
assert irow["dimension"] == "item"
assert irow["item_id"] == "1072639258886"
assert irow["entity_key"] == irow["item_id"]          # 唯一键用的就是宝贝ID
assert irow["unit_id"] == "83708697345"               # 单元ID 另存, 不覆盖宝贝ID
assert irow["campaign_id"] == "83392769388"
assert irow["entity_name"] == "性感收腰透视蕾丝吊带睡裙"
assert irow["charge"] == 9.81 and irow["ctr_percent"] == 3.869

# 单元当天没有任何投放数据 → 接口只回 {"roi7d":0}，没有 charge 键。这种行不写。
assert map_adgroup_row({"adgroupId": 1, "campaignId": 2,
                        "reportInfoList": [{"roi7d": 0.0}]}, "d", "keyword", 1, "s")[1] == "no_data"
assert map_adgroup_row({"adgroupId": 1, "campaignId": 2}, "d", "keyword", 1, "s")[1] == "no_data"
assert map_adgroup_row({"adgroupId": 1, "reportInfoList": [INFO]}, "d", "keyword", 1, "s")[1] == "no_campaign"

# 宝贝ID 取值优先级: materialId > bindItemId > parentItemId > adgroupId
assert item_id_of({"material": {"materialId": 111, "bindItemId": 222}}) == "111"
assert item_id_of({"material": {"bindItemId": 222}}) == "222"
assert item_id_of({"material": {"parentItemId": 333}}) == "333"
assert item_id_of({"adgroupId": 444}) == "444"
assert item_id_of({}) == ""
assert map_adgroup_row({"adgroupId": None, "campaignId": 9,
                        "reportInfoList": [INFO]}, "d", "keyword", 1, "s")[1] == "no_item_id"

# ---- 分页: 507 个单元 / 每页 200 → 3 页 ----
assert should_page(507, 200) == [0, 200, 400]
assert should_page(200, 200) == [0]
assert should_page(0, 200) == [0]
assert should_page(None, 200) == [0]
assert should_page(3, 0) == [0, 1, 2]      # page_size 被夹到 1, 不能除零

print("OK: collect_alimama_promo 纯函数全部断言通过")
