"""1688 选品配置"""

# 1688 选品用 tb-auto 的 9222 Chrome(已登录 1688), 与抖店任务(9223)分流
CDP_URL = "http://127.0.0.1:9222"

# 类目 -> 关键词(可继续扩)。女装为重点(秋冬),放首位优先采
CATEGORIES = {
    "女装": ["牛仔短裤", "半身裙", "连衣裙", "皮草", "棉衣", "毛衣",
             "牛仔裤", "休闲裤", "阔腿裤", "加绒裤",
             "皮草马甲", "皮草斗篷",
             "羽绒服", "呢子大衣"],
    "帽子": ["遮阳帽", "棒球帽", "贝雷帽", "渔夫帽", "草帽",
             "羊毛帽", "贝雷帽高端", "真皮帽", "羊绒帽", "水貂毛帽", "礼帽", "草编帽", "高端棒球帽"],
    "睡衣": ["睡衣", "睡袍", "家居睡衣", "情侣睡衣", "真丝睡衣"],
    "家居服": ["家居服套装", "棉家居服", "法式家居服", "居家服女"],
    "美甲": ["穿戴甲", "美甲贴片", "美甲工具", "甲油胶", "美甲饰品",
             "穿戴甲高端", "手工穿戴甲", "精品穿戴甲", "穿戴甲定制", "穿戴甲礼盒", "穿戴甲套装"],
    "口红": ["口红", "唇釉", "唇膏", "哑光口红", "丝绒唇釉", "水光唇釉",
             "口红套装", "口红礼盒", "雾面口红", "染唇液", "口红管", "迷你口红"],
}

# 类目最低价过滤(元):低于该价格的商品不入库。低价+退货运费=亏钱。
# 帽子/美甲转中高客单价;女装/睡衣/家居服客单价本就够,不限(0 表示不限制)
MIN_PRICE = {
    "帽子": 20,
    "美甲": 15,
    "口红": 15,
    "女装": 0,
    "睡衣": 0,
    "家居服": 0,
}

# 硬筛:诚信通年限(搜索页可拿到的唯一硬筛)
MIN_TRUST_YEARS = 3

# 优质等级门槛(grade_quality.py 与 import_to_db.py 共用)。repurchase 为百分数(如40=40%)
# 商品(仅 data_source=1 1688搜索候选参评; ISV行指标NULL不分级): 取最高匹配级
PRODUCT_GRADE_A = {"trust": 7, "repurchase": 40, "sales": 5000}
PRODUCT_GRADE_B = {"trust": 7, "repurchase": 40, "sales": 1000}
PRODUCT_GRADE_C = {"trust": 5, "repurchase": 30, "sales": 500}
# 厂家(platform_type=1) - A 是 B 的超集(A=B条件+更严), 保证 A⊂B 严格层级
FACTORY_GRADE_A = {"trust": 7, "repurchase": 40, "total_sales": 10000, "product_count": 20}
FACTORY_GRADE_B = {"trust": 5, "repurchase": 30, "total_sales": 10000}
# 导入门槛: 只入库优质(商品C+ / 厂家B+), 非优质留 jsonl 不入库

# 每个关键词翻多少页(每页约 60 个商品);抗限流,不宜过高
MAX_PAGES_PER_KW = 8

# 风控节奏(秒)——慢节奏抗限流
PAGE_DELAY_MIN, PAGE_DELAY_MAX = 15, 25
SCROLL_TIMES = 3
SCROLL_WAIT = 2
PAGE_LOAD_WAIT = 3

# 输出
OUT_DIR = "/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/output"
