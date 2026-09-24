#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_in_stock_current 纯逻辑自检: URL/OUT 映射与参数解析. 直跑: venv/bin/python test_collect_list.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_mappings():
    import collect_in_stock_current as c
    assert 'sold_out' in c.URLS and 'SellManage/sold_out' in c.URLS['sold_out']
    assert 'in_stock' in c.URLS and 'SellManage/in_stock' in c.URLS['in_stock']
    assert c.OUT_FILES['sold_out'].endswith('taobao_onsale_current.jsonl')
    assert c.OUT_FILES['in_stock'].endswith('taobao_in_stock_current.jsonl')


def test_parse_args_default():
    import collect_in_stock_current as c
    lists, rest = c.parse_lists(['--limit', '5'])
    assert lists == ['in_stock']          # 默认行为不变
    lists2, rest2 = c.parse_lists(['--list', 'both', '--limit', '5'])
    assert lists2 == ['in_stock', 'sold_out']
    assert rest2 == ['--limit', '5']
    lists3, _ = c.parse_lists(['--list', 'sold_out'])
    assert lists3 == ['sold_out']


if __name__ == '__main__':
    test_mappings()
    test_parse_args_default()
    print('PASS: collect list mappings/args')
