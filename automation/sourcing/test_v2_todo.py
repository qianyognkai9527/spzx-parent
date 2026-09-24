#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2 build_todo 纯逻辑自检. 直跑: venv/bin/python test_v2_todo.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assign_shop_category_v2 import build_todo


def prog():
    return {'done': ['d1'], 'skipped': ['s1'], 'failed': {'f1': {'category': 'x', 'error': 'e'}},
            'noprice': [], 'sizegap': {}}


PLAN = [
    {'itemId': 'w1', 'category': '长裤', 'pool': 'warehouse'},
    {'itemId': 'f1', 'category': '美甲', 'pool': 'onsale'},      # failed -> 尾部
    {'itemId': 'o1', 'category': '美甲', 'pool': 'onsale'},
    {'itemId': 'g1', 'category': 'other', 'pool': 'gone'},       # gone -> 无 --ids 剔除
    {'itemId': 'd1', 'category': '长裤', 'pool': 'warehouse'},   # done -> 剔除
    {'itemId': 's1', 'category': '美甲', 'pool': 'onsale'},      # skipped -> 剔除(--ids 放行)
    {'itemId': 'o2', 'category': 'other', 'pool': 'onsale'},     # onsale -> 前部(无 pool 用例见 test_legacy_no_pool_field)
]


def test_order_and_filter():
    todo = build_todo(PLAN, prog(), retry_failed=True)
    ids = [r['itemId'] for r in todo]
    assert 'd1' not in ids and 's1' not in ids     # done/skipped 剔除
    assert 'g1' not in ids                         # gone 池剔除
    assert ids == ['o1', 'o2', 'w1', 'f1']         # onsale -> warehouse -> failed


def test_limit_hits_onsale_head():
    todo = build_todo(PLAN, prog(), retry_failed=True, limit=2)
    assert [r['itemId'] for r in todo] == ['o1', 'o2']   # 排序后切片, 探路命中出售中


def test_no_retry_failed_excludes():
    todo = build_todo(PLAN, prog(), retry_failed=False)
    assert 'f1' not in [r['itemId'] for r in todo]


def test_legacy_no_pool_field():
    plan = [{'itemId': 'x1', 'category': '长裤'}]        # 旧 plan 无 pool
    todo = build_todo(plan, prog())
    assert [r['itemId'] for r in todo] == ['x1']         # 按 warehouse 兜底, 不报错


def test_ids_filter():
    # --ids 选中子集、保持排序、done 仍被剔除
    todo = build_todo(PLAN, prog(), retry_failed=True, ids=['w1', 'd1', 'o2', 'f1'])
    assert [r['itemId'] for r in todo] == ['o2', 'w1', 'f1']   # onsale->warehouse->failed, d1(done)剔除
    todo2 = build_todo(PLAN, prog(), retry_failed=True, ids=['o1', 'w1'])
    assert [r['itemId'] for r in todo2] == ['o1', 'w1']        # 未命中 ids 的(failed 重试与否)不出现
    todo3 = build_todo(PLAN, prog(), ids=['o1', 'f1'])          # 不带 retry_failed: failed 剔除
    assert [r['itemId'] for r in todo3] == ['o1']
    todo4 = build_todo(PLAN, prog(), retry_failed=True, ids=['nope'])
    assert todo4 == []                                          # 无命中返回空


def test_ids_admits_skipped():
    # --ids 定向时 skipped 放行(人工修完数据补跑); done 仍剔除
    todo = build_todo(PLAN, prog(), retry_failed=True, ids=['s1'])
    assert [r['itemId'] for r in todo] == ['s1']
    todo2 = build_todo(PLAN, prog(), retry_failed=True, ids=['d1'])
    assert todo2 == []


def test_gone_excluded():
    # gone 池无 --ids 剔除(编辑页打不开); 显式 --ids 放行
    todo = build_todo(PLAN, prog(), retry_failed=True)
    assert 'g1' not in [r['itemId'] for r in todo]
    todo2 = build_todo(PLAN, prog(), retry_failed=True, ids=['g1'])
    assert [r['itemId'] for r in todo2] == ['g1']


if __name__ == '__main__':
    test_order_and_filter()
    test_limit_hits_onsale_head()
    test_no_retry_failed_excludes()
    test_legacy_no_pool_field()
    test_ids_filter()
    test_ids_admits_skipped()
    test_gone_excluded()
    print('PASS: v2 build_todo')
