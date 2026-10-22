#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""import_offer_map 纯函数单测（无网络无 DB，仓库惯例：python 直跑）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_offer_map import parse_offer_id  # noqa: E402


def test_parse_offer_id():
    assert parse_offer_id("https://detail.1688.com/offer/980287802829.html") == 980287802829
    assert parse_offer_id("https://detail.1688.com/offer/123.html?spm=x") == 123
    assert parse_offer_id("http://detail.1688.com/offer/456.html") == 456
    assert parse_offer_id("") is None
    assert parse_offer_id(None) is None
    assert parse_offer_id("https://tb.com/x") is None


def test_parse_offer_id_real_mixed_urls():
    # 库里也存过非 offer 形态的 1688 URL，不能误解析
    assert parse_offer_id("https://www.1688.com/") is None
    assert parse_offer_id("https://detail.1688.com/offer/0.html") == 0


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("all ok")
