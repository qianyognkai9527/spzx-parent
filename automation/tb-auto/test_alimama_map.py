#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_alimama_promo 纯函数自检. 跑法: automation/venv/bin/python test_alimama_map.py

fixture 用的是 2026-10-03 实测抓到的真实一行(标准计划B / 2026-10-01), 不是编的:
charge=9.809999999999999 adPv=827 click=32 ctr=0.03869 ecpc=0.30656 ecpm=11.86215
"""
from collect_alimama_promo import (cast, crowd_body, date_range, hit_risk, is_standard, item_id_of,
                                   map_adgroup_row, map_crowd_row, map_row, map_word_row,
                                   should_page, wants_crowd, wants_item, wants_word, word_body)

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

# ---- 人群层: 一个 (单元,人群) 节点 → 一行 promo_cost_item_daily ----
CROWD_INFO = {"charge": 9.81, "adPv": 100.0, "click": 3.0, "ctr": 0.03, "ecpc": 3.27,
              "ecpm": 98.1, "alipayInshopAmt": 0.0, "alipayInshopNum": 0.0,
              "cartInshopNum": 1.0, "itemColInshopNum": 0.0, "shopColDirNum": 0.0,
              "colNum": 0.0, "itemColCart": 0.0, "addNewUv": 0,
              "adgroupId": 83440680802, "adgroupName": "纯色轻奢皮草外套女秋冬韩版立领慵懒风",
              "crowdName": "三级女30_34L4"}
CROWD_ROW = {"adgroupId": 83440680802, "campaignId": 83392643008, "crowdId": 29063497481,
             "onlineStatus": 1, "crowdInterval": "< 5%", "price": {"discount": 300},
             "crowd": {"crowdName": "三级女30_34L4", "crowdValue": "108087233",
                       "label": {"optionList": [{"optionDesc": "30-34岁"}]}},
             "reportInfoList": [CROWD_INFO]}
CADG = {"adgroupId": 83440680802, "adgroupName": "纯色轻奢皮草外套女秋冬韩版立领慵懒风",
        "campaignId": 83392643008, "campaignName": "6脉之D标准自选词控点击拉新",
        "material": {"materialId": 1072639258886}}

crow, creason = map_crowd_row(CROWD_ROW, CADG, "2026-10-11", 1, "keyword",
                              "alimama-crowd:onebpSearch")
assert creason is None and crow is not None
assert crow["dimension"] == "crowd"
assert crow["plan_type"] == "keyword"                   # 不是 'crowd'(那是产品线名)
assert crow["entity_key"] == "83440680802:29063497481"  # 复合键, crowdId 单用不唯一
assert crow["entity_id"] == "29063497481"
assert crow["entity_name"] == "三级女30_34L4"
assert crow["item_id"] == "1072639258886"               # item_id 来自单元(material)
assert crow["item_name"] == CADG["adgroupName"]
assert crow["unit_id"] == "83440680802"
assert crow["campaign_id"] == "83392643008"
assert crow["report_source"] == "alimama-crowd:onebpSearch"
assert crow["charge"] == 9.81 and crow["click"] == 3 and crow["ad_pv"] == 100
assert crow["ctr_percent"] == 3.0
assert crow["raw_json"].find("crowdInterval") >= 0 and crow["raw_json"].find("discount") >= 0

# reportInfoList 空 / 没有 charge 键 → 当天该人群没投放数据, 不写 0 行
assert map_crowd_row({"adgroupId": 1, "crowdId": 2, "reportInfoList": None},
                     CADG, "d", 1, "keyword", "s")[1] == "no_data"
assert map_crowd_row({"adgroupId": 1, "crowdId": 2, "reportInfoList": [{"roi7d": 0}]},
                     CADG, "d", 1, "keyword", "s")[1] == "no_data"
# 缺 crowdId(复合键少一半) → 跳过
assert map_crowd_row({"adgroupId": 1, "reportInfoList": [CROWD_INFO]},
                     CADG, "d", 1, "keyword", "s")[1] == "no_crowd_id"
# 计划 id 在 crowd 行与 adgroup 上都没有 → 跳过
BARE = {"adgroupId": 1, "adgroupName": "x", "material": {"materialId": 111}}
assert map_crowd_row({"adgroupId": 1, "crowdId": 2, "reportInfoList": [CROWD_INFO]},
                     BARE, "d", 1, "keyword", "s")[1] == "no_campaign"
# 单元连 item_id 都拿不到 → 跳过
assert map_crowd_row(CROWD_ROW, {"adgroupName": "x"},
                     "d", 1, "keyword", "s")[1] == "no_item_id"

# ---- 人群请求体: sourceList 必须在 rptQuery.conditionList 里, 且不给 adgroupIdList ----
cb = crowd_body({"body": {"csrfId": "C", "loginPointId": "L"}},
                "onebpSearch", 83392643008, "2026-10-11", 0, 500)
assert cb["rptQuery"]["conditionList"][0]["sourceList"] == ["adgroup_detail", "crowd_list"]
assert "adgroupIdList" not in cb
assert cb["campaignIdList"] == ["83392643008"]
assert cb["csrfId"] == "C" and cb["loginPointId"] == "L"
assert cb["rptQuery"]["conditionList"][0]["isRt"] is False

# ---- level 门 ----
assert wants_item("item") and wants_item("both") and wants_item("crowd") and wants_item("all")
assert not wants_item("campaign")
assert wants_crowd("crowd") and wants_crowd("all")
assert not wants_crowd("campaign") and not wants_crowd("item") and not wants_crowd("both")

# ---- 词层: 一个 (单元,词) 节点 → 一行 promo_cost_item_daily ----
# fixture 是按「与 crowd 层同构」的预期形态编的; 探针(Task 1)若发现字段名不同,
# 这里和 word_of/word_body 一起改 —— 两条必须同步, 否则单测绿了采集还是错。
WORD_INFO = {"charge": 5.4, "adPv": 60.0, "click": 7.0, "ctr": 0.1167, "ecpc": 0.7714,
             "alipayInshopAmt": 0.0, "alipayInshopNum": 0.0, "cartInshopNum": 1.0,
             "itemColInshopNum": 1.0, "colNum": 1.0, "bidwordId": 987654321,
             "word": "皮草外套女"}
WORD_ROW = {"adgroupId": 83440680802, "campaignId": 84290744044, "bidwordId": 987654321,
            "word": "皮草外套女", "matchScope": 4, "reportInfoList": [WORD_INFO]}
WADG = {"adgroupId": 83440680802, "adgroupName": "纯色轻奢皮草外套女秋冬韩版立领慵懒风",
        "campaignId": 84290744044, "campaignName": "6脉之E标准词提价拉新",
        "material": {"materialId": 1072639258886}}

wrow, wreason = map_word_row(WORD_ROW, WADG, "2026-10-17", 1, "keyword",
                             "alimama-keyword:onebpSearch")
assert wreason is None and wrow is not None
assert wrow["dimension"] == "keyword"
assert wrow["entity_key"] == "83440680802:皮草外套女"   # 复合键: 同词多单元不互踩
assert wrow["entity_id"] == "987654321"
assert wrow["entity_name"] == "皮草外套女"
assert wrow["item_id"] == "1072639258886"               # item_id 来自单元(material)
assert wrow["unit_id"] == "83440680802"
assert wrow["campaign_id"] == "84290744044"
assert wrow["report_source"] == "alimama-keyword:onebpSearch"
assert wrow["charge"] == 5.4 and wrow["click"] == 7 and wrow["cpc"] == 0.7714
# 没有词文本 → 键不完整, 跳过
assert map_word_row({"adgroupId": 1, "campaignId": 2, "reportInfoList": [WORD_INFO]},
                    WADG, "d", 1, "keyword", "s")[1] == "no_word"
# 空 reportInfoList / 无 charge 键 = 当天没投放, 不写 0 行(与 item/crowd 同口径)
assert map_word_row({"adgroupId": 1, "bidwordId": 2, "word": "w", "reportInfoList": None},
                    WADG, "d", 1, "keyword", "s")[1] == "no_data"
assert map_word_row({"adgroupId": 1, "bidwordId": 2, "word": "w",
                     "reportInfoList": [{"roi7d": 0}]},
                    WADG, "d", 1, "keyword", "s")[1] == "no_data"
# 单元拿不到 item_id → 跳过
assert map_word_row(WORD_ROW, {"adgroupName": "x"}, "d", 1, "keyword", "s")[1] == "no_item_id"

# ---- 词请求体: sourceList 必须在 rptQuery.conditionList 里; 逐单元传 adgroupIdList(实测必填) ----
wb = word_body({"body": {"csrfId": "C", "loginPointId": "L"}},
               "onebpSearch", 84290744044, "2026-10-17", 0, 500, 83440680802)
assert wb["rptQuery"]["conditionList"][0]["sourceList"] == ["adgroup_detail", "bidword_list"]
assert wb["campaignIdList"] == ["84290744044"]
assert wb["adgroupIdList"] == ["83440680802"]
assert wb["csrfId"] == "C" and wb["loginPointId"] == "L"
assert wb["rptQuery"]["conditionList"][0]["isRt"] is False

# ---- level 门: word 含在 all 里; word 依赖 item(要 join 单元拿 item_id) ----
assert wants_word("word") and wants_word("all")
assert not wants_word("campaign") and not wants_word("item")
assert not wants_word("crowd") and not wants_word("both")
assert wants_item("word")

print("OK: collect_alimama_promo 纯函数全部断言通过")
