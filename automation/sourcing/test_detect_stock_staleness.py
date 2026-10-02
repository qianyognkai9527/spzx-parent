#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""detect_stock_change 到期判定与进度格式的纯函数自检.
跑法: automation/venv/bin/python test_detect_stock_staleness.py

守的是这次真实故障：进度名单写成"永久 done"后，变化检测每天扫 0 个还报 success，
库存数据悄悄腐烂了七周才被发现。所以"哪些货源该重查"必须是可单测的纯函数。
"""
from datetime import date, timedelta

from detect_stock_change import due_by_staleness

TODAY = date(2026, 10, 3)

# 从未查过 / 刚查过 / 到期 —— 三种都要判对
checked = {
    101: "2026-10-02",   # 1 天前，7 天窗口内 → 不重查
    102: "2026-09-20",   # 13 天前 → 重查
    103: "2026-09-26",   # 7 天前，正好等于窗口 → 重查（>= 才算到期）
    104: "2026-10-03",   # 今天 → 不重查
}
due = due_by_staleness(checked, 7, today=TODAY)
assert due == {102, 103}, due
# 没出现在 checked 里的（如 105）由调用方按"未查过"处理，不在这里判
assert 105 not in due

# 窗口调大调小的方向不能反：1 天窗口下"昨天查过"的 101 也到期，今天查过的 104 仍不重查
assert due_by_staleness(checked, 30, today=TODAY) == set()
assert due_by_staleness(checked, 1, today=TODAY) == {101, 102, 103}

# 脏数据一律判"该重查"：宁可多查一次，也不能让一条坏记录把某个货源永久排除
assert due_by_staleness({201: "", 202: None, 203: "not-a-date", 204: "2026-13-45"}, 7,
                        today=TODAY) == {201, 202, 203, 204}
# 带时间的 ISO 串要能读（前 10 位是日期）
assert due_by_staleness({301: "2026-09-01T08:30:00"}, 7, today=TODAY) == {301}
assert due_by_staleness({}, 7, today=TODAY) == set()

# 空进度（旧的永久 done 格式会被读成空）→ 全部到期，首轮就会把 315 个池子重查一遍
assert due_by_staleness({}, 7, today=TODAY) == set()

print("OK: 到期判定纯函数全部断言通过")
