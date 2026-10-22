import unittest
from sync_onsale import parse_row_text, parse_chip_counts, pages_for, diff_bindings

SAMPLE_ROW = ("预览\n【梦回千禧】复古设计随性豹纹绒感整皮真兔毛皮草外套女秋冬大衣\n"
              "ID：1073885580706\n复制\n货号：XYPK106豹纹兔毛长袖\n\n \n晟昀皮草行\n"
              "\t销售中\t358元\t48\t是\t\n编辑店铺商品\n更换货源\n更多")
SAMPLE_ROW_SHOP_PRICE = ("预览\n2026新款豹纹整皮真兔毛皮草外套女中长款\nID：1093333948278\n"
                         "复制\n同步记录\n销售中\nAI内容优化\n已匹配 1024元 48\n开启")
SAMPLE_CHIPS = ("快捷筛选：\n销售中(889)\n仓库中(2947)\n已关联货源(3831)\n未关联货源(1)\n"
                "关联货源已下架(222)\n价格倒挂(60)")

class TestParse(unittest.TestCase):
    def test_row_full(self):
        r = parse_row_text(SAMPLE_ROW)
        self.assertEqual(r["taobao_item_id"], 1073885580706)
        self.assertEqual(r["source_status"], "销售中")
        self.assertEqual(r["source_price"], 358.0)
        self.assertEqual(r["source_stock"], 48)

    def test_row_shop_price_not_stolen(self):
        """店铺侧 价格(1024元) 不跟在状态词后面 → 不得当货源三元组"""
        r = parse_row_text(SAMPLE_ROW_SHOP_PRICE)
        self.assertEqual(r["taobao_item_id"], 1093333948278)
        self.assertEqual(r["source_status"], "")
        self.assertIsNone(r["source_price"])
        self.assertIsNone(r["source_stock"])

    def test_row_no_item(self):
        self.assertIsNone(parse_row_text("无ID的行"))

    def test_row_without_triple(self):
        r = parse_row_text("ID：1093333948278\n其他")
        self.assertEqual(r["taobao_item_id"], 1093333948278)
        self.assertEqual(r["source_status"], "")
        self.assertIsNone(r["source_price"])

    def test_chips(self):
        c = parse_chip_counts(SAMPLE_CHIPS)
        self.assertEqual(c["销售中"], 889)
        self.assertEqual(c["仓库中"], 2947)
        self.assertEqual(c["价格倒挂"], 60)
        self.assertIsNone(c.get("不存在筛选"))

    def test_pages(self):
        self.assertEqual(pages_for(889), 9)
        self.assertEqual(pages_for(100), 1)
        self.assertEqual(pages_for(0), 0)

    def test_diff(self):
        new, gone = diff_bindings({1, 2, 3}, {2, 3, 4})
        self.assertEqual(new, {1})
        self.assertEqual(gone, {4})

if __name__ == "__main__":
    unittest.main()
