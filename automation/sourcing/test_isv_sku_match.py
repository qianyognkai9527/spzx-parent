#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""isv_sku_match 纯函数单测（无网络，仓库惯例：python 直跑）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isv_sku_match import parse_spec_name, analyze_rows, upsert, manual_csv_rows  # noqa: E402


def test_parse_spec_name():
    assert parse_spec_name("预览 2XL 灰色 价格：36.39元 库存：10000") == "2XL 灰色"
    assert parse_spec_name("价格：36.39元") == ""
    assert parse_spec_name("预览 M 价格：1元 库存：2") == "M"


def test_analyze_rows_count_mismatch_and_unmatched():
    rows = [{"name": "M", "status": "已匹配", "bound": "灰色-M"},
            {"name": "L", "status": "未匹配", "bound": ""}]
    a = analyze_rows(rows, ["灰色-M", "灰色-L", "灰色-XL"])
    assert a["taobao_count"] == 2 and a["offer_count"] == 3
    assert a["count_mismatch"] is True
    assert a["unmatched"] == ["L"]


def test_analyze_rows_duplicate_binding():
    rows = [{"name": "M", "status": "已匹配", "bound": "灰色-M"},
            {"name": "L", "status": "已匹配", "bound": "灰色-M"}]
    a = analyze_rows(rows, ["灰色-M"])
    assert a["duplicates"] == ["灰色-M"]
    # 2 个淘宝 SKU 对 1 个 1688 规格, 数量确实不等 → 计数不等与重复绑定同时成立
    assert a["count_mismatch"] is True


def test_analyze_rows_no_offer_specs():
    a = analyze_rows([{"name": "M", "status": "已匹配", "bound": "灰色-M"}], None, None)
    assert a["count_mismatch"] is None and a["offer_count"] is None


def test_analyze_rows_offer_count_estimate():
    # DB 没有该 offer, 用选择器 radio 组数乘积估算
    rows = [{"name": "M", "status": "已匹配", "bound": "灰色-M"},
            {"name": "L", "status": "已匹配", "bound": "灰色-L"}]
    a = analyze_rows(rows, None, offer_count=4)
    assert a["offer_count"] == 4 and a["count_mismatch"] is True
    a2 = analyze_rows(rows, None, offer_count=2)
    assert a2["count_mismatch"] is False


def test_upsert_dedupes_by_item():
    rep = {"items": []}
    upsert(rep, "1", {"item_id": "1", "status": "dry"})
    upsert(rep, "1", {"item_id": "1", "status": "manual_needed", "unmatched": ["L"]})
    upsert(rep, "2", {"item_id": "2", "status": "count_mismatch", "title": "T"})
    assert len(rep["items"]) == 2
    assert rep["items"][0]["status"] == "manual_needed"


def test_manual_csv_rows():
    rep = {"items": [
        {"item_id": "9", "title": "T9", "status": "manual_needed", "unmatched": ["L"],
         "count_mismatch": True, "taobao_sku_count": 2, "offer_spec_count": 3},
        {"item_id": "8", "title": "T8", "status": "count_mismatch",
         "taobao_sku_count": 5, "offer_spec_count": 4},
        {"item_id": "7", "title": "T7", "status": "ok"},
        {"item_id": "6", "title": "T6", "status": "open_fail", "note": "open_fail"},
    ]}
    rows = manual_csv_rows(rep)
    assert rows[0][:4] == ["9", "T9", "manual_needed", "L"]
    assert rows[1][2] == "count_mismatch"            # manual_needed 且数量不等 → 补一行
    assert rows[2][:3] == ["8", "T8", "count_mismatch"]
    assert rows[3][:3] == ["6", "T6", "open_fail"]
    assert all(r[0] != "7" for r in rows)            # ok 不进人工清单


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("all ok")
