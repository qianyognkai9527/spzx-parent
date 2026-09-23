"""
规则模块 - 款号生成 + 属性推断 + 标题改写
"""
import random
import re
import string


# 需从标题中去除的品牌(可扩)
BRAND_REMOVE = ["瑰若"]

# 1688 痕迹词
TRACE_WORDS = ["铺货", "代发", "批发", "厂家直销", "一件代发", "现货"]


def rewrite_title(title):
    """规则改写淘宝标题:去品牌、去货号/1688痕迹、去重、控长≤30字符。返回改写后标题。"""
    if not title:
        return title
    t = title.strip()
    # 去品牌
    for b in BRAND_REMOVE:
        t = t.replace(b, "")
    # 去货号: 字母+数字(如 P3772, L6934, XK6246)
    t = re.sub(r"[A-Za-z]{1,3}\d{3,5}", "", t)
    # 去 ID：XXX / ID:XXX
    t = re.sub(r"ID[：:]\s*\d+", "", t, flags=re.IGNORECASE)
    # 去连续4位以上纯数字(尾号如1899)
    t = re.sub(r"\d{4,}", "", t)
    # 去1688痕迹词
    for kw in TRACE_WORDS:
        t = t.replace(kw, "")
    # 去多余空格
    t = re.sub(r"\s+", "", t).strip()
    # 控长≤30
    if len(t) > 30:
        t = t[:30]
    return t


def generate_style_number():
    """生成款号: 2个大写字母 + 3位数字
    - 数字不能以4开头
    - 数字不能包含38
    """
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    while True:
        d1 = random.randint(0, 9)
        if d1 == 4:
            continue
        d2 = random.randint(0, 9)
        d3 = random.randint(0, 9)
        digits = f"{d1}{d2}{d3}"
        if "38" not in digits:
            return letters + digits


def infer_attributes(title):
    """根据商品标题推断属性"""
    attrs = {}
    title_lower = title.lower()

    # 季节
    if any(k in title for k in ['夏', '短', '薄', '透气', '冰丝', '清凉']):
        attrs['season'] = '夏季'
    elif any(k in title for k in ['冬', '加厚', '保暖', '绒', '夹棉']):
        attrs['season'] = '冬季'
    elif any(k in title for k in ['春', '秋', '长袖']):
        attrs['season'] = '春秋'

    # 材质 (注意: 先检查多字关键词，避免"蕾丝"被"丝"匹配)
    if '冰丝' in title:
        attrs['material'] = '冰丝'
    elif '蕾丝' in title:
        attrs['material'] = '蕾丝'
    elif '棉' in title:
        attrs['material'] = '棉'
    elif any(k in title for k in ['丝绸', '真丝', 'silk']):
        attrs['material'] = '丝绸'
    elif any(k in title for k in ['聚酯', '涤纶']):
        attrs['material'] = '聚酯纤维'
    elif any(k in title for k in ['锦纶', '尼龙']):
        attrs['material'] = '锦纶'
    elif any(k in title for k in ['麻', 'linen']):
        attrs['material'] = '麻'
    elif any(k in title for k in ['雪纺', 'chiffon']):
        attrs['material'] = '雪纺'

    # 性别
    if '女' in title:
        attrs['gender'] = '女'
    elif '男' in title:
        attrs['gender'] = '男'

    # 风格
    if any(k in title for k in ['性感', '诱惑', '低胸', '透视']):
        attrs['style'] = '性感'
    elif any(k in title for k in ['可爱', '甜美', '公主']):
        attrs['style'] = '甜美'
    elif any(k in title for k in ['简约', '基础', '纯色']):
        attrs['style'] = '简约'
    elif any(k in title for k in ['复古', '法式']):
        attrs['style'] = '复古'
    elif any(k in title for k in ['运动', '休闲']):
        attrs['style'] = '休闲'

    # 领型
    if 'V领' in title or 'v领' in title_lower:
        attrs['collar'] = 'V领'
    elif '圆领' in title:
        attrs['collar'] = '圆领'
    elif '高领' in title:
        attrs['collar'] = '高领'
    elif '一字领' in title:
        attrs['collar'] = '一字领'

    # 裙型
    if 'a字' in title.lower() or 'a字裙' in title:
        attrs['skirt_type'] = 'A字裙'
    elif '连衣裙' in title:
        attrs['skirt_type'] = '连衣裙'
    elif '半身裙' in title:
        attrs['skirt_type'] = '半身裙'

    # 商品类型(睡衣/家居服/女装等)
    if '睡裙' in title:
        attrs['type'] = '睡裙'
    elif '家居服' in title or '居家服' in title:
        attrs['type'] = '家居服'
    elif '睡衣' in title or '睡袍' in title:
        attrs['type'] = '睡衣'
    elif '吊带' in title and '裙' in title:
        attrs['type'] = '吊带裙'
    elif '短裤' in title:
        attrs['type'] = '短裤'
    elif '套装' in title:
        attrs['type'] = '套装'

    # 领型/版型(补充)
    if '露背' in title:
        attrs['neckline'] = '露背'
    elif '深v' in title.lower():
        attrs['neckline'] = '深V'
    elif '吊带' in title:
        attrs['neckline'] = '吊带'
    elif '系带' in title or '绑带' in title:
        attrs['neckline'] = '系带'

    # 特点(可多个)
    features = []
    if '透气' in title:
        features.append('透气')
    if '聚拢' in title:
        features.append('聚拢')
    if '加胸垫' in title or '带胸垫' in title or '胸垫' in title:
        features.append('加胸垫')
    if '收腰' in title:
        features.append('收腰')
    if '防晒' in title:
        features.append('防晒')
    if features:
        attrs['features'] = '/'.join(features)

    return attrs


if __name__ == "__main__":
    for i in range(10):
        print(f"款号 {i+1}: {generate_style_number()}")

    print()
    test_titles = [
        "瑰若情趣内衣慵懒舒适蕾丝性感诱惑低胸透视网纱睡裙女套装190",
        "夏季新款纯棉圆领短袖T恤女",
        "冬季加厚保暖法兰绒睡衣男",
    ]
    for t in test_titles:
        print(f"\n标题: {t}")
        print(f"  推断: {infer_attributes(t)}")
