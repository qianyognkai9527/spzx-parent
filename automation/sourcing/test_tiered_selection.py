#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_stock_change import select_tiered  # noqa: E402

U = [(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, "e")]

def test_t1_low_stock_and_never_checked():
    # 库存<100 → T1; 从未查过 → T1; 无SKU(NULL) → T1
    # (brief 原稿 min_stocks 漏了 pid 2 的记录；按 select_tiered 语义"无SKU→T1"，
    #  已查过但无 SKU 记录也会进 T1，故补 2:500 使 pid 2 = 查过且库存充足、不进 T1)
    t1, t2, t3 = select_tiered(U, {2: "2026-10-17"}, {1: 50, 2: 500, 3: None}, set(), 100, 100)
    assert t1 == [1, 3, 4, 5] and t2 == [] and t3 == []

def test_t2_rotation():
    # 库存充足且查过 → 只在 (pid+doy)%7==0 时进 T2
    checked = {1: "2026-10-17", 2: "2026-10-17", 3: "2026-10-17", 4: "2026-10-17", 5: "2026-10-17"}
    min_stocks = {1: 500, 2: 800, 3: 300, 4: 999, 5: 200}
    t1, t2, t3 = select_tiered(U, checked, min_stocks, set(), day_of_year=0, t1_threshold=100)
    assert t1 == []
    assert t2 == [p for p in (1, 2, 3, 4, 5) if p % 7 == 0]      # doy=0 → pid%7==0
    _, t2b, _ = select_tiered(U, checked, min_stocks, set(), day_of_year=1, t1_threshold=100)
    assert t2b == [p for p in (1, 2, 3, 4, 5) if (p + 1) % 7 == 0]

def test_t3_dead_only_on_monday():
    checked = {1: "2026-10-17"}
    t1, t2, t3 = select_tiered(U, checked, {1: 500}, {2, 3}, 100, 100, monday=False)
    assert 2 not in t1 + t2 + t3 and 3 not in t1 + t2 + t3        # 非周一死链不占额度
    t1, t2, t3 = select_tiered(U, checked, {1: 500}, {2, 3}, 100, 100, monday=True)
    assert t3 == [2, 3]

if __name__ == "__main__":
    test_t1_low_stock_and_never_checked(); test_t2_rotation(); test_t3_dead_only_on_monday()
    print("test_tiered_selection: 3/3 PASS")
