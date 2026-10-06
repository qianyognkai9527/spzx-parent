#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdd_map 纯函数自检. 跑法: automation/venv/bin/python test_pdd_map.py"""
import pdd_config as _C
from pdd_map import (
    clean_pdd_title,
    fit_pdd_title,
    hit_brand,
    hit_offcategory,
    pdd_price,
    pdd_price_cost,
    strip_b2b,
)

# 价格 ×1.3 四舍五入到 2 位
assert pdd_price(10) == 13.0
assert pdd_price(9.99) == 12.99          # 12.987 -> 12.99
assert pdd_price("19.9") == 25.87        # 25.87
assert pdd_price(0) is None
assert pdd_price(-3) is None
assert pdd_price(None) is None
assert pdd_price("abc") is None

# 标题清洗: 去首尾空白 + 折叠多空格
assert clean_pdd_title("  美甲  穿戴甲 ") == "美甲 穿戴甲"
assert clean_pdd_title("") == ""

# ---- 1688 成本倒推定价(常数见 pdd_config: 快递3 / 费率0.6% / 损耗3% / 毛利40%) ----
DENOM = 1 - _C.PLATFORM_FEE - _C.REFUND_LOSS - _C.TARGET_MARGIN
assert pdd_price_cost(16) == round((16 + _C.FREIGHT_DEFAULT) / DENOM, 2)
assert pdd_price_cost(16, freight=0) == round(16 / DENOM, 2)
assert pdd_price_cost("16.5") == round((16.5 + _C.FREIGHT_DEFAULT) / DENOM, 2)
assert pdd_price_cost(0) is None
assert pdd_price_cost(None) is None
assert pdd_price_cost("abc") is None
# MIN_MARKUP 只在倒推价低于「进价+快递+底价」时兜住: 进价越高倒推价越占优
assert pdd_price_cost(440) == round((440 + _C.FREIGHT_DEFAULT) / DENOM, 2)

# 毛利被配到 >=100% 时分母 <=0, 必须返回 None 而不是算出负价上架
_orig = _C.TARGET_MARGIN
try:
    _C.TARGET_MARGIN = 0.99
    assert pdd_price_cost(16) is None
finally:
    _C.TARGET_MARGIN = _orig

# ---- 标题: 大牌词识别 + 60 字符按词界截断 ----
assert hit_brand("奈姿 手工穿戴甲miumiu小香") == ["miumiu"]
assert hit_brand("手工穿戴甲 猫眼 纯色") == []
assert hit_brand("") == []
# 克罗心/奶芙芙 是店里真实驳回过的词(2026-10-05 拿"已驳回"清单反查), 必须在黑名单里;
# 而"奈姿"是 1688 供应商名, 72 条带它的商品全部在售 —— 千万别因为它出现在驳回标题里就一起拉黑。
assert hit_brand("甜酷气质风裸杏奶茶色磨砂钢珠克罗心穿戴甲") == ["克罗心"]
assert hit_brand("奈姿 纯手工光疗穿戴甲奶芙芙成品重复使用美甲贴片") == ["奶芙芙"]
assert hit_brand("奈姿 纯手工穿戴甲秋冬新款蜜雪法式蝴蝶猫眼") == []
assert "chrome hearts" in [w.lower() for w in _C.BRAND_WORDS]
assert len(fit_pdd_title("甲" * 100)) <= 60
assert fit_pdd_title("穿戴甲 猫眼 手工 " + "甲" * 55).endswith("手工")

# ---- 品类过滤: 配件/工具/脚甲不能挂穿戴甲类目, 但"带水钻的穿戴甲"要留 ----
assert set(hit_offcategory("穿戴甲收纳盒 pe悬浮盒 饰品盒子")) == {"收纳", "盒子", "饰品盒"}
assert hit_offcategory("手工穿戴甲脚甲十四片法式蝴蝶钻") == ["脚甲"]
assert hit_offcategory("纯手工光疗穿戴甲烫金蝴蝶美甲贴片") == []
# 「钻」是甲片装饰不是卖钻, 列进黑名单会把 86 条好货源误杀
assert hit_offcategory("薄荷汽水浮雕蝴蝶钻穿戴甲") == []

# ---- 1688 的 B2B/跨平台词要抹掉 ----
assert strip_b2b("手工穿戴甲 批发 成品 重复使用") == "手工穿戴甲 成品 重复使用"
assert "亚马逊" not in strip_b2b("跨境亚马逊手工穿戴甲")
assert strip_b2b("穿戴甲 厂家直销") == "穿戴甲"
assert strip_b2b("纯手工光疗穿戴美甲高端猫眼系列批发成品") == "纯手工光疗穿戴美甲高端猫眼系列成品"

# ---- 1688 直铺定价: 进价 × 系数(默认 5.0) ----
from pdd_map import pdd_price_markup  # noqa: E402
assert pdd_price_markup(9) == 45.0
assert pdd_price_markup(12.5) == 62.5
assert pdd_price_markup(9, factor=2.5) == 22.5
assert pdd_price_markup(0) is None
assert pdd_price_markup(None) is None
assert pdd_price_markup("abc") is None

print("OK: pdd_map 全部断言通过")
