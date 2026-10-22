#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""offer_fetch 纯函数单测（仓库惯例：python 直跑，无网络）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from offer_fetch import is_gone, parse_skus, extract_meta  # noqa: E402


def test_is_gone():
    assert is_gone("很抱歉，您查看的商品已下架")
    assert is_gone("宝贝已下架 or 商品不存在")
    assert is_gone("此商品已删除")
    assert is_gone("无法查看该商品")
    assert not is_gone("正常商品标题 库存999件")           # 正常页不算
    assert not is_gone("请登录后查看")                     # 登录页≠下架（collect_1688_full 同款守卫）
    assert not is_gone("安全验证")                         # 风控页≠下架
    assert not is_gone("")
    assert not is_gone(None)


def test_parse_skus():
    payload = '{"data":{"skuSelectorBizModel":{"skuInfoMap":{"M &gt; 白":{"skuId":"111","canBookCount":5,"price":12.5,"specId":"s1"},"XL 红":{"skuId":"222","canBookCount":0,"price":13,"specId":"s2"}}}}}'
    skus = parse_skus(payload)
    assert skus[0]["sku_key"] == "M > 白" and skus[0]["stock"] == 5
    assert skus[1]["stock"] == 0 and skus[1]["sku_id"] == "222"
    assert parse_skus("不是json") == []
    assert parse_skus('{"data":{}}') == []


def test_extract_meta():
    title, img = extract_meta("纯欲蕾丝睡裙-阿里巴巴", "https://cbu01.alicdn.com/x.jpg")
    assert title == "纯欲蕾丝睡裙" and img.endswith(".jpg")
    # 没有分隔符的标题原样保留；超 200 截断
    assert extract_meta("无分隔标题", None)[0] == "无分隔标题"
    long_t = "字" * 300
    assert len(extract_meta(long_t, None)[0]) == 200


if __name__ == "__main__":
    test_is_gone(); test_parse_skus(); test_extract_meta()
    print("test_offer_fetch: 3/3 PASS")
