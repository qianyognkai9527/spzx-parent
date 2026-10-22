#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decide 纯函数单测（spec 2026-10-19-schedule-optimization §5）"""
import unittest
from stock_event_check import WHITELIST, decide


def rows(*items):
    # items: (alert_type, days_ago)
    import time
    out = []
    for t, d in items:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() - d * 86400))
        out.append({"alert_type": t, "status": 0, "create_time": ts})
    return out


class TestDecide(unittest.TestCase):
    def test_today_whitelist_hit(self):
        ok, why = decide(rows(("source_dead", 0)), True)
        self.assertTrue(ok)

    def test_low_stock_no_longer_triggers(self):
        # 2026-10-19 owner 决定: low_stock 属每日重算常规状态, 移出事件白名单
        ok, why = decide(rows(("low_stock", 0)), True)
        self.assertFalse(ok)

    def test_oversell_risk_no_longer_triggers(self):
        # 2026-10-19 owner 决定: oversell_risk 同上, 当日超卖由次日 03:00 基线兜底
        ok, why = decide(rows(("oversell_risk", 0)), True)
        self.assertFalse(ok)

    def test_old_unread_ignored(self):
        ok, why = decide(rows(("source_dead", 3)), True)
        self.assertFalse(ok)

    def test_non_whitelist_ignored(self):
        ok, why = decide(rows(("ingest_stale", 0)), True)
        self.assertFalse(ok)

    def test_read_alert_ignored(self):
        import time
        r = [{"alert_type": "source_dead", "status": 1,
              "create_time": time.strftime('%Y-%m-%d %H:%M:%S')}]
        ok, why = decide(r, True)
        self.assertFalse(ok)

    def test_no_success_batch_triggers(self):
        ok, why = decide([], False)
        self.assertTrue(ok)

    def test_all_clear(self):
        ok, why = decide([], True)
        self.assertFalse(ok)

    def test_whitelist_members(self):
        self.assertEqual(WHITELIST, {"isv_sync_fail", "source_dead",
                                     "onsale_binding_change", "onsale_mismatch"})


if __name__ == "__main__":
    unittest.main()
