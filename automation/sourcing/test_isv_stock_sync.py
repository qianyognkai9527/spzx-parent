#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page_select_ok 纯函数单测（spec 2026-10-19-schedule-optimization §4.3）"""
import unittest
from isv_stock_sync import page_select_ok


class TestPageSelectOk(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(page_select_ok(["已选100/100"], 100))

    def test_with_suffix(self):
        self.assertTrue(page_select_ok(["已选100/共100"], 100))

    def test_zero_selected_is_bad(self):
        self.assertFalse(page_select_ok(["已选0/100"], 100))

    def test_partial_is_bad(self):
        self.assertFalse(page_select_ok(["已选37/100"], 100))

    def test_empty_sel(self):
        self.assertFalse(page_select_ok([], 100))

    def test_none_sel(self):
        self.assertFalse(page_select_ok(None, 100))

    def test_unrelated_text(self):
        self.assertFalse(page_select_ok(["已关联货源(4183)"], 100))


if __name__ == "__main__":
    unittest.main()
