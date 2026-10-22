#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backfill_offer_archive import build_product_row, OFFER_RE  # noqa: E402


def test_offer_re():
    assert OFFER_RE.search("https://detail.1688.com/offer/980287802829.html").group(1) == "980287802829"
    assert OFFER_RE.search("https://detail.1688.com/page/index.htm") is None


def test_build_product_row_alive():
    offer = {"skus": [{"sku_key": "M", "stock": 5, "price": 12.5}],
             "gone": False, "title": "测试睡裙", "img": "https://x/y.jpg"}
    row = build_product_row("980287802829", offer)
    # (name, code, url, price, freight, img, source_status, data_source, platform_type)
    assert row[0] == "测试睡裙" and row[1] == "980287802829"
    assert row[2].endswith("/offer/980287802829.html")
    assert row[3] == 12.5 and row[4] == 8          # 货源价=最低SKU价; 运费定值8(D4)
    assert row[6] == 1 and row[7] == 2 and row[8] == 1   # source_status=1, data_source=2, platform_type=1


def test_build_product_row_gone():
    offer = {"skus": [], "gone": True, "title": "已下架商品", "img": None}
    row = build_product_row("123", offer)
    assert row[6] == 0                              # 死链建档但标记失效
    assert row[3] == 0                              # 无价格记 0，不猜


if __name__ == "__main__":
    test_offer_re(); test_build_product_row_alive(); test_build_product_row_gone()
    print("test_backfill_offer_archive: 3/3 PASS")
