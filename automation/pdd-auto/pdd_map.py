#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 铺货纯函数: 价格换算、标题清洗、字段映射.

定价常数走 `import pdd_config as C` 而不是 from-import: 这样调参只改 pdd_config,
也允许单测在运行时改常数验证边界(比如毛利 >=100% 必须算不出价)。
"""
import pdd_config as C


def pdd_price(taobao_price):
    """淘宝价 × PRICE_FACTOR, 四舍五入到 2 位. 非法/<=0 返回 None."""
    try:
        v = float(taobao_price)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return round(v * C.PRICE_FACTOR, 2)


def pdd_price_cost(source_price, freight=None):
    """1688 进价 → 拼多多拼单价(成本倒推).

    拼单价 = (进价 + 快递) / (1 - 平台费率 - 仅退款损耗 - 目标毛利), 再兜一层 MIN_MARKUP.
    分母可能因常数配错而 <=0, 那样算出来是负数或无穷, 所以夹住并返回 None 让调用方跳过,
    而不是把一个假价格铺上架。
    """
    try:
        cost = float(source_price)
    except (TypeError, ValueError):
        return None
    if cost <= 0:
        return None
    ship = C.FREIGHT_DEFAULT if freight is None else float(freight)
    denom = 1 - C.PLATFORM_FEE - C.REFUND_LOSS - C.TARGET_MARGIN
    if denom <= 0:
        return None
    price = (cost + ship) / denom
    return round(max(price, cost + ship + C.MIN_MARKUP), 2)


def pdd_price_markup(source_price, factor=None):
    """1688 直铺定价: 进价 × 系数(默认 C.PRICE_FACTOR_1688). 非法/<=0 返回 None."""
    f = C.PRICE_FACTOR_1688 if factor is None else factor
    try:
        v = float(source_price)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return round(v * f, 2)


def clean_pdd_title(title):
    """去首尾空白 + 折叠连续空白为一个空格."""
    return " ".join((title or "").split())


def hit_brand(title):
    """标题命中的他人大牌名(小写比对), 没命中返回 [].

    1061 条美甲货源里只 1 条带 miumiu, 但拼多多按侵权处理是直接下架扣分, 代价不对称。
    """
    t = (title or "").lower()
    return [w for w in C.BRAND_WORDS if w in t]


def hit_offcategory(title):
    """命中的配件/工具/脚甲词 —— 这类货挂进穿戴甲类目就是类目错放."""
    t = title or ""
    return [w for w in C.CATEGORY_EXCLUDE if w in t]


def strip_b2b(title):
    """删掉 1688 标题里的批发/跨平台词(零售场景不该有).

    替换成空串而不是空格: 中文标题里这些词通常前后无空格, 换成空格会凭空断开词组。
    """
    t = clean_pdd_title(title)
    for w in C.B2B_WORDS:
        t = t.replace(w, "")
    return clean_pdd_title(t)


def fit_pdd_title(title, limit=60):
    """PDD 标题上限 60 字符(30 汉字), 超了按空格边界截, 不拦腰断词."""
    t = clean_pdd_title(title)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip() or t[:limit]

