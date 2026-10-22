#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_alerts import dead_alert_message  # noqa: E402


def test_message_contains_names_and_items():
    m = dead_alert_message("瑰若睡裙", 123, [1071, 1072])
    assert "瑰若睡裙" in m and "123" in m and "1071" in m and "1072" in m
    assert "人工" in m          # D1: 失效只告警, 处理是人工
    m2 = dead_alert_message(None, 55, [])
    assert "55" in m2           # 无名货源回退 sp_id


if __name__ == "__main__":
    test_message_contains_names_and_items(); print("test_detect_source_dead: PASS")
