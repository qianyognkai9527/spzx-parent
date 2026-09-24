#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_shop_cat_plan 合并逻辑自检. 直跑: venv/bin/python test_plan_merge.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_shop_cat_plan import build_merge_plan, classify


def test_old_category_preserved():
    old = [{'itemId': '1', 'title': '纯棉睡衣女', 'category': '秋冬款'}]  # 旧判定故意与新规则不同
    instock = [('1', '纯棉睡衣女')]
    onsale = []
    plan, new_n = build_merge_plan(old, instock, onsale)
    assert new_n == 0
    rec = [p for p in plan if p['itemId'] == '1'][0]
    assert rec['category'] == '秋冬款'          # 原样保留, 不重判
    assert rec['pool'] == 'warehouse'


def test_new_items_classified_and_pool():
    old = []
    instock = [('2', '珊瑚绒睡裙女冬季加厚')]
    onsale = [('3', '穿戴甲成品手工甲片'), ('4', '牛仔短裤女夏季')]
    plan, new_n = build_merge_plan(old, instock, onsale)
    assert new_n == 3
    m = {p['itemId']: p for p in plan}
    assert m['2']['category'] == classify('珊瑚绒睡裙女冬季加厚') and m['2']['pool'] == 'warehouse'
    assert m['3']['category'] == '美甲' and m['3']['pool'] == 'onsale'
    assert m['4']['category'] == '牛仔短裤' and m['4']['pool'] == 'onsale'


def test_gone_and_onsale_priority():
    old = [{'itemId': '5', 'title': 'x', 'category': 'other'}]
    plan, _ = build_merge_plan(old, [], [])           # 两个池都没有 -> gone
    assert plan[0]['pool'] == 'gone'
    old2 = [{'itemId': '6', 'title': 'x', 'category': 'other'}]
    plan2, _ = build_merge_plan(old2, [('6', 'x')], [('6', 'x')])  # 双池同时出现 -> onsale 优先
    assert plan2[0]['pool'] == 'onsale'


if __name__ == '__main__':
    test_old_category_preserved()
    test_new_items_classified_and_pool()
    test_gone_and_onsale_priority()
    print('PASS: plan merge')
