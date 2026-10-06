#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B/C 规则自检(纯函数): 新必填属性/SKU列取值 + detect_gaps 内联识别. 跑法: venv/bin/python test_bc_rules.py"""
from compliance_filler import FIELD_ZONE, ZONE_PROP, ZONE_SKU, parse_gaps, prop_value_for, sku_value_for

# 1. 新字段入位
for f in ('适用人群', '风格', '是否带胸垫'):
    assert FIELD_ZONE.get(f) == ZONE_PROP, f'{f} 未入 ZONE_PROP'
for f in ('裙长', '适用体型'):
    assert FIELD_ZONE.get(f) == ZONE_SKU, f'{f} 未入 ZONE_SKU'

# 2. parse_gaps 能从内联错误文本识别(detect_gaps 读 body.innerText 含内联)
gaps = parse_gaps('必填项适用人群不能为空\n必填项风格不能为空\n必填项是否带胸垫不能为空')
assert {'适用人群', '风格', '是否带胸垫'} <= {g['name'] for g in gaps}
gaps2 = parse_gaps('蓝色 - XL：裙长不能为空。\n米白色 - M：适用体型不能为空。')
assert {'裙长', '适用体型'} <= {g['name'] for g in gaps2}

# 3. 属性取值规则
assert prop_value_for('是否带胸垫', '蕾丝文胸带胸垫聚拢')[0] == '是'
assert prop_value_for('是否带胸垫', '纯棉吊带背心')[-1] == '否'
assert prop_value_for('适用人群', '大码胖mm牛仔短裤')[0] == '特殊体型女性'
assert prop_value_for('适用人群', '运动瑜伽健身裤')[0] == '运动爱好者'
assert prop_value_for('适用人群', '学生少女初中生')[0] == '青少年女性'
assert prop_value_for('适用人群', '现货温柔蕾丝背心女')[-1] == '成年女性'   # 兜底
assert prop_value_for('风格', '温柔风针织开衫')[0] == '优雅风'
assert prop_value_for('风格', '宽松慵懒风卫衣')[0] == '休闲风'
assert prop_value_for('风格', '无特征标题')[-1] == '休闲风'                  # 兜底

# 4. SKU 列取值(选项=实地核读)
assert sku_value_for('裙长', '立体蝴蝶结牛仔短裙女', ['中长裙款', '超长裙', '短裙', '中裙', '长裙']) == '短裙'
assert sku_value_for('裙长', '法式碎花连衣裙', ['中长裙款', '超长裙', '短裙', '中裙', '长裙']) == '中裙'  # 兜底
assert sku_value_for('适用体型', '露肩亮片连衣裙', ['修身型', '梨型', '直筒型', '通用型']) == '通用型'   # 兜底
assert sku_value_for('裤长', '蚕丝羊绒窄版直筒裤', ['七分裤', '短裤', '长裤']) == '长裤'   # 语义别名
assert sku_value_for('裤长', '毛边牛仔短裤女', ['七分裤', '短裤', '长裤']) == '短裤'
assert sku_value_for('裤长', '无长度线索标题', ['七分裤', '短裤', '长裤']) is None          # 留人工

# 5. 既有规则不回归
assert prop_value_for('是否商场同款', '') == ['否']
assert prop_value_for('功能', '加绒保暖睡衣')[0] == '保暖'
assert prop_value_for('适用场景', '睡衣家居服')[0] == '居家'
print('OK: B/C 规则 22 断言全过')

# 6. 图案(半身裙/牛仔类必填 SKU 列)
assert FIELD_ZONE.get('图案') == ZONE_SKU
assert sku_value_for('图案', '立体蝴蝶结牛仔短裙', ['几何图形', '条纹', '爱心', '纯色', '花卉']) == '纯色'  # 兜底
assert sku_value_for('图案', '碎花连衣裙', ['几何图形', '碎花', '爱心', '纯色']) == '碎花'
assert sku_value_for('图案', '条纹polo领', ['条纹', '纯色']) == '条纹'
print('OK: 图案规则 3 断言过')
