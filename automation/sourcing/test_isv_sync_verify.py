#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from isv_sync_verify import parse_sync_record  # noqa: E402


def test_parse_sync_record():
    v, n = parse_sync_record("商品库存同步为352，M 白色规格库存同步为286")
    assert v == 1 and n == [352, 286]
    v, n = parse_sync_record("商品库存同步为0")
    assert v == 1 and n == [0]
    assert parse_sync_record("同步失败：网络异常")[0] == 3
    assert parse_sync_record("今天天气不错")[0] == 2
    assert parse_sync_record("")[0] == 2
    assert parse_sync_record(None)[0] == 2

if __name__ == "__main__":
    test_parse_sync_record(); print("test_isv_sync_verify: PASS")
