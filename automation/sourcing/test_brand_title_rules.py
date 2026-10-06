#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brand_title_rules 自检. 直跑: venv/bin/python test_brand_title_rules.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brand_title_rules import ensure_guiruo_prefix, dedup_targets, merge_progress


def test_prefix_added_when_missing():
    assert ensure_guiruo_prefix('性感蕾丝睡裙女') == '瑰若性感蕾丝睡裙女'


def test_prefix_not_duplicated():
    assert ensure_guiruo_prefix('瑰若性感蕾丝睡裙女') == '瑰若性感蕾丝睡裙女'


def test_prefix_stripped_when_in_middle():
    # 旧标题品牌词不在开头: 去重后前置, 不出现两次
    out = ensure_guiruo_prefix('性感瑰若蕾丝睡裙')
    assert out.startswith('瑰若') and out.count('瑰若') == 1


def test_prefix_empty_title():
    assert ensure_guiruo_prefix('') == '瑰若'


def test_prefix_truncates_to_max():
    out = ensure_guiruo_prefix('甲' * 100, max_len=30)
    assert len(out) == 30 and out.startswith('瑰若')


def test_dedup_onsale_wins():
    rows = [
        {'itemId': '1', 'title': 'a', 'pool': 'warehouse'},
        {'itemId': '1', 'title': 'b', 'pool': 'onsale'},
        {'itemId': '2', 'title': 'c', 'pool': 'warehouse'},
    ]
    out = {r['itemId']: r for r in dedup_targets(rows)}
    assert len(out) == 2
    assert out['1']['pool'] == 'onsale' and out['1']['title'] == 'b'


def test_merge_progress_failed_pruned_by_done():
    disk = {'done': ['1'], 'skipped': [], 'failed': {'1': {'error': 'x'}, '2': {'error': 'y'}}}
    prog = {'done': ['3'], 'skipped': ['2'], 'failed': {'3': {'error': 'z'}}}
    m = merge_progress(disk, prog)
    assert set(m['done']) == {'1', '3'}
    assert set(m['skipped']) == {'2'}
    assert list(m['failed'].keys()) == []  # 1 done / 2 skipped 被剔除, 3 也 done


if __name__ == '__main__':
    test_prefix_added_when_missing()
    test_prefix_not_duplicated()
    test_prefix_stripped_when_in_middle()
    test_prefix_empty_title()
    test_prefix_truncates_to_max()
    test_dedup_onsale_wins()
    test_merge_progress_failed_pruned_by_done()
    print('PASS: brand_title_rules')
