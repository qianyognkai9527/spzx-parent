import unittest
from detect_stock_night import select_night_pool

ROWS = [
    {"pid": 1, "offer": "101", "stock": 5, "status": "销售中"},
    {"pid": 2, "offer": "102", "stock": 0, "status": "销售中"},
    {"pid": 3, "offer": "103", "stock": 500, "status": "销售中"},
    {"pid": 4, "offer": "104", "stock": 30, "status": "销售中"},
    {"pid": 5, "offer": "105", "stock": 200, "status": "已下架"},
    {"pid": 6, "offer": "106", "stock": None, "status": "销售中"},
]

class TestSelect(unittest.TestCase):
    def test_pool_split(self):
        inspect, control, dead = select_night_pool(ROWS, low_threshold=10, control_n=2, seed=1)
        self.assertEqual({r["pid"] for r in inspect}, {1, 2, 6})   # 低库存 + 未知库存都巡检
        self.assertEqual({r["pid"] for r in dead}, {5})            # 已下架不开页面
        self.assertEqual(len(control), 2)                          # 健康池随机对照
        self.assertTrue(all(r["pid"] in (3, 4) for r in control))

    def test_control_zero(self):
        inspect, control, dead = select_night_pool(ROWS, low_threshold=10, control_n=0, seed=1)
        self.assertEqual(control, [])

    def test_no_overshoot(self):
        """对照池只从健康池抽, 不与巡检/死链重叠"""
        inspect, control, dead = select_night_pool(ROWS, low_threshold=10, control_n=10, seed=7)
        pids = {r["pid"] for r in control}
        self.assertEqual(pids, {3, 4})  # 健康池只有 2 个, 全取也不越界

    def test_bad_status_ignored(self):
        rows = [{"pid": 9, "offer": "109", "stock": 1, "status": "仓库中"}]
        inspect, control, dead = select_night_pool(rows, low_threshold=10, control_n=5, seed=1)
        self.assertEqual((inspect, control, dead), ([], [], []))

if __name__ == "__main__":
    unittest.main()
