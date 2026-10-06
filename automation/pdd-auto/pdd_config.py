#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDD 铺货配置: 端口/路径/系数集中一处."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SOURCING = os.path.abspath(os.path.join(BASE, "..", "sourcing"))

CDP_PORT = 9224
# 1688 详情页要走 sourcing 那条线的 Chrome（9223），登录态在 sourcing/chrome-profile-sourcing
CDP_PORT_SOURCING = 9223
PROFILE = os.path.join(BASE, "chrome-profile")

PRICE_FACTOR = 1.3            # 淘宝价 × 1.3
PRICE_FACTOR_1688 = 5.0       # 1688 直铺: 进价 × 5 = 拼单价
PDD_CATEGORY = "穿戴甲"
# 发布目标类目(第一步「查看更多推荐」展开后按此全串点选)
TARGET_CATEGORY = "彩妆/香水/美妆工具 > 指甲贴/穿戴甲 > 手工穿戴甲"

MMS_HOME = "https://mms.pinduoduo.com/"
# 发布入口: 第一步=上传主图+标题+选类目 → 下一步 → 完善商品信息
MMS_GOODS_PUBLISH = "https://mms.pinduoduo.com/goods/category"
MMS_GOODS_LIST = "https://mms.pinduoduo.com/goods/goods_list"

# ---- 无人值守节奏(2026-10-05 加, 之前一条都没有) ----
# 一件铺完到下一件的间隔: 10-02 那轮是连成 5 件后第 6 件弹验证码, 说明频率本身就是触发条件。
ITEM_GAP_SEC = 25
# 同一件被验证码卡到第 N 次就隔离(转 failed 不再重投)。重试不是无副作用的:
# 966442252934 在 10-02 重试了 4 轮, 每轮都把表单填到底再卡在验证码上, 草稿箱因此留下两条同名草稿。
CAPTCHA_QUARANTINE_AFTER = 2
# 连续多少件都卡验证码 => 判定是账号级风控而非单件问题, 交外层冷却。
CAPTCHA_STREAK_STOP = 3
# 刚弹过验证码, 下一件之前多等一会
CAPTCHA_BACKOFF_SEC = 120
# 第 1 次触发验证码时在窗口前等多久, 留给现场的人去过验证; 同一件第 2 次触发就不再等
# （那时它已经注定被隔离, 盲等纯浪费 —— 无人值守时每次验证码白扔 5 分钟）
CAPTCHA_WAIT_SEC = 300
# 事件等待（快路）：把 "睡 N 秒赌页面好了" 换成 "条件成立就走"。
# 实测单件 ~88s 里约 44s 是固定 sleep；置 False 即回到全部固定等待（踩坑时的回退开关）。
# 实测 A/B（2026-10-05，同一件商品、--test 只走填表不提交）：固定等待 36s/件 -> 事件等待 19~20s/件。
# 注意：光把 sleep 换成轮询会**更慢**（第一次改完是 46s）—— 流程跑到页面前面去了，
# 上传指示一出现就立刻填标题，页面异步逻辑会把值清掉、Tab 白按、推荐区整页不渲染（等 30s 也没有）。
# 现在靠 ensure_category_recommendations 回读标题 + 重填重试解决。踩坑时置 0 回退到固定等待。
FAST_WAIT = os.environ.get("PDD_FAST_WAIT", "1") != "0"

TAOBAO_DATA = os.path.join(BASE, "taobao_product_data.jsonl")
WORKLIST = os.path.join(BASE, "pdd_worklist.jsonl")
PDD_PRODUCTS = os.path.join(BASE, "pdd_products.jsonl")
PROGRESS = os.path.join(BASE, "pdd_create_progress.json")
NOTES = os.path.join(BASE, "pdd_notes")

# ---- 1688 货源直铺(美甲/穿戴甲) ----
# 数据源是 sourcing 侧的选品清单, 字段只有 offerId/title/source_price/img_uris/consign/category,
# 没有运费也没有 SKU 库存(1061 条里只有 168 条进了 source_product 且 freight_cost 全 NULL),
# 所以定价只能走下面的成本倒推常数。
MEIJIA_WORKLIST = os.path.join(SOURCING, "1688_meijia_worklist.jsonl")
WORKLIST_1688 = os.path.join(BASE, "pdd_worklist_1688.jsonl")
IMG_ROOT_1688 = os.path.join(BASE, "pdd_images_1688")
PROGRESS_1688 = os.path.join(BASE, "pdd_create_progress_1688.json")
# 店铺核对的两个数据文件：在售快照 + 累积驳回台账（都由 sync_pdd_store.py 写）
SNAPSHOT = os.path.join(BASE, "pdd_store_snapshot.json")
REJECTIONS = os.path.join(BASE, "pdd_rejections.json")

# ---- 1688 货源直铺定价(美甲/穿戴甲) ----
# 数据源侧只有进价: 1061 条货源里只有 168 条进了 source_product 且 freight_cost 全 NULL、0 条有 SKU,
# `fee_benchmark` 以前也没有拼多多的行(2026-10-05 补了一条 0.6%)。
# **生效的是上面的 PRICE_FACTOR_1688 = 5.0（进价 ×5）**, 下面这组成本倒推常数只有 pdd_price_cost 在用,
# 而 pdd_price_cost 目前只被单测调用 —— 别以为改 TARGET_MARGIN 就能改在售价。
FREIGHT_DEFAULT = 3.0     # 1688 一件代发快递费(穿戴甲轻小件, 库里无数据, 按经验值)
# 拼多多技术服务费。同一个 0.6% 在库里也有一份: `fee_benchmark`(platform_type=3, 美甲),
# 商品运营台的预估毛利读的是那一份。改这里不改那里, 定价和毛利就会各说各话。
PLATFORM_FEE = 0.006      # 拼多多技术服务费 0.6%
REFUND_LOSS = 0.03        # 仅退款/退货损耗预提
TARGET_MARGIN = 0.40      # 目标毛利率
MIN_MARKUP = 2.0          # 拼单价至少高于(进价+运费)这么多, 兜住上面三项估漏的情况

# 「商品参考价」= 拼单价 × 本系数。这个字段拼多多必填且必须大于最大单买价,
# 以前 1.5 直接写死在 create_pdd_product.fill_step2 里, 看不出它是会给消费者看的划线价。
# 合规口径(《明码标价和禁止价格欺诈规定》市场监管总局令第56号):
#   第十六条 被比较价格应真实准确; 未标明详情的, 不得高于同一经营场所比较前七日内的最低成交价格。
#   第十七条 不得用无依据或无从比较的价格作为折价基准或被比较价格。
#   第二十三条 违反十六至二十条按 价格法/反不正当竞争法/电子商务法 等处罚(2026 年多地市监已就虚假划线价立案处罚)。
# 我们这批新品**没有任何成交记录**(order_info 还是 2023 演示数据), 所以 ×1.5 得到的参考价
# 正落在"无依据的被比较价格"上。要收口就降到 单买价 + 0.01(仍满足平台"必须大于单买价"),
# 但那会改掉已在售 146+ 件的价签观感与转化 —— 属经营决定, 这里先只把它变成可改的一行。
REF_PRICE_FACTOR = 1.5

# 标题里的他人大牌名 —— 拼多多按假货/侵权处理是直接扣分下架, 宁可不铺
BRAND_WORDS = ("miumiu", "chanel", "香奈儿", "dior", "迪奥", "gucci", "prada",
               "hermes", "爱马仕", "tiffany", "卡地亚", "celine", "fendi", "ysl",
               # 2026-10-05 用店里"已驳回"清单反查出来的真凶, 不是猜的:
               # 克罗心(Chrome Hearts)三条、奶芙芙两条被驳"需提交品牌来源凭证", 而同批 72 条
               # 带供应商名"奈姿"的商品全部在售 —— 所以 奈姿 是安全的, 这两个才是品牌管控词。
               "克罗心", "奶芙芙", "chrome hearts")

# 非穿戴甲本体(配件/工具/脚甲): 1061 条里这类占约 1%, 但挂进「指甲贴/穿戴甲>手工穿戴甲」
# 就是类目错放, 而且 0.5 元的收纳盒按成本倒推会挂成 6.21 元, 看着像铺货垃圾。
# 注意「钻」不能列进来 —— 1004 条穿戴甲里 86 条标题带"钻", 指的是甲片上的水钻装饰, 不是卖钻。
CATEGORY_EXCLUDE = ("收纳", "包装盒", "盒子", "饰品盒", "配件", "工具", "清洁", "卸甲",
                    "胶水", "甲托", "展示", "训练", "模型", "脚甲", "趾甲", "脚趾")

# 1688 标题里的 B2B/跨平台词: 拼多多是零售场景, 带"批发/厂家直销"拉低点击,
# 带其他平台名(亚马逊/淘宝/抖店)会被判站外引流。
B2B_WORDS = ("批发", "一件代发", "厂家直销", "货源", "工厂", "外贸", "跨境",
             "亚马逊", "淘宝", "天猫", "京东", "拼多多", "抖店", "抖音", "快手", "独立站", "ebay", "aliexpress")
