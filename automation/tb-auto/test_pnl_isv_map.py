#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_offer_items 单测: 纯 assert 风格, 直接运行。
跑法: automation/venv/bin/python automation/tb-auto/test_pnl_isv_map.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pnl_common import merge_offer_items

# 1) 并集去重, OSR 在前
m, c = merge_offer_items([("111", "A")], [("222", "B"), ("111", "A")])
assert m == {"111": ["A"], "222": ["B"]}, m
assert c == [], c

# 2) 同 offer 不同 item → 都保留, 记冲突
m, c = merge_offer_items([("111", "A")], [("111", "B")])
assert m["111"] == ["A", "B"], m
assert c == [("111", "A", "B")], c

# 3) 空值过滤
m, c = merge_offer_items([], [(None, "X"), ("", "Y"), ("333", "")])
assert m == {}, m
assert c == [], c

# 4) OSR 自身重复 offer 去重
m, c = merge_offer_items([("111", "A"), ("111", "A")], [])
assert m == {"111": ["A"]}, m

print("test_pnl_isv_map OK")
