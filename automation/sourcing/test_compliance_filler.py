#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compliance_filler 纯逻辑自检. 直跑: venv/bin/python test_compliance_filler.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compliance_filler import parse_gaps, is_image_only_failure

BODY = """
基础信息
1
商品属性
必填项未填
销售信息
3
销售规格
必填项未填
物流服务
1
提取方式
必填项未填
面料
必填项面料不能为空
厚薄不能为空
白色 - M：厚薄不能为空。
功能
必填项功能不能为空
是否商场同款
必填项是否商场同款不能为空
"""


def test_parse_gaps_known_fields():
    gaps = parse_gaps(BODY)
    names = {g['name'] for g in gaps}
    assert '厚薄' in names and '面料' in names and '提取方式' in names
    assert '功能' in names and '是否商场同款' in names
    zones = {g['name']: g['zone'] for g in gaps}
    assert zones['厚薄'] == 'sku'
    assert zones['提取方式'] == 'extract'
    assert zones['面料'] == 'prop'


def test_parse_gaps_no_false_positive():
    assert parse_gaps('全部字段已填写完成，厚薄=常规') == []
    assert parse_gaps('') == []


def test_parse_gaps_inline_separate():
    # 真实页面形态(1072552474230 实测): 字段 label 行后隔 7 行出现独立错误行「必填项不能为空」
    body = """物流服务
模板
发货时间
提取方式
*
使用物流配送
为了提升消费者购物体验，淘宝要求全网商品设置运费模板，如何使用模板，查看视频教程
使用官方寄件，集合多家运力，一键发货更便捷、全程保障价更低。点击体验
电子交易凭证
电子凭证管理后台 亲，请谨慎设置有效期
必填项不能为空
区域限售
"""
    gaps = parse_gaps(body)
    names = {g['name'] for g in gaps}
    assert '提取方式' in names
    assert {g['zone'] for g in gaps if g['name'] == '提取方式'} == {'extract'}
    # 错误行前更近的其他字段 label 应优先归属, 不误判更远的字段
    body2 = """提取方式
*
使用物流配送
功能
必填项不能为空
"""
    names2 = {g['name'] for g in parse_gaps(body2)}
    assert '功能' in names2 and '提取方式' not in names2


def test_image_only():
    assert is_image_only_failure('提交失败: 数据问题: ...CHK_IMAGE_PC_PIC_STEAL...mainImagesGroup...')
    assert not is_image_only_failure('CHK_IMAGE_PC_PIC_STEAL 销售规格 必填项未填')
    assert not is_image_only_failure('提交失败: 数据问题: 商品发布 错误(4) 销售规格 必填项未填')
    # F-C: 混合错误(盗图+其他类错误码/视频/尺码)不误转 skipped 待换图队列
    assert not is_image_only_failure('提交失败: 数据问题: ...CHK_IMAGE_PC_PIC_STEAL...CHK_SKU_PARAM_ENUM_ERROR...')
    assert not is_image_only_failure('PIC_STEAL 视频比例错误')
    assert not is_image_only_failure('PIC_STEAL 尺码表数据缺失')


def test_sku_value_for():
    from compliance_filler import sku_value_for
    assert sku_value_for('是否加绒', '冬季加绒加厚卫裤') == '是'
    assert sku_value_for('是否加绒', '夏季薄款牛仔裤') == '否'
    assert sku_value_for('厚薄', '任意标题') == '常规'
    assert sku_value_for('款式', '任意标题') is not None   # 面板第一项, 运行时取


def test_sku_value_for_options():
    from compliance_filler import sku_value_for
    # 厚薄: options 含'常规'用'常规', 不含回落第一项(选项以面板实况为准)
    assert sku_value_for('厚薄', 't', ['薄款', '常规', '厚款']) == '常规'
    assert sku_value_for('厚薄', 't', ['薄款', '适中']) == '薄款'
    # 款式: 无默认值, options 第一项
    assert sku_value_for('款式', 't', ['A款', 'B款']) == 'A款'
    # 是否加绒: 标题派生, 与 options 无关
    assert sku_value_for('是否加绒', '加绒保暖卫裤', ['是', '否']) == '是'
    assert sku_value_for('是否加绒', '薄款冰丝裤', ['是', '否']) == '否'


def test_sku_value_for_unknown_fields():
    from compliance_filler import sku_value_for
    # F-B: 未知字段(裤型/裤长等)标题公共子串(≥2 连续中文)匹配优先, 无匹配返回 None 绝不写首项猜测值
    assert sku_value_for('裤长', '春秋九分牛仔裤', ['超短裤', '短裤', '九分裤', '长裤']) == '九分裤'
    assert sku_value_for('裤型', '无关标题', ['短裤', '阔腿裤']) is None
    assert sku_value_for('裤型', '无关标题', []) is None
    assert sku_value_for('裤长', '无关标题', ['超短裤', '短裤', '九分裤', '长裤']) is None
    # 命名字段回归: 是否加绒 标题派生不受影响
    assert sku_value_for('是否加绒', '冬季加绒裤') == '是'


def test_prop_values():
    from compliance_filler import prop_value_for, season_value
    s = season_value()
    assert '年' in s and '季' in s            # 如 2026年秋季
    assert prop_value_for('是否商场同款', 'x') == ['否']
    # notes 差异: 面料=普通属性下拉(p-20551/p-587227907, 实值 牛仔布/聚酯纤维), 非材质成分组合
    assert prop_value_for('面料', 'x') == ['聚酯纤维']
    assert prop_value_for('面料', '牛仔短裤女夏') == ['牛仔布', '聚酯纤维']
    # 材质成分=组合 UI, 取值格式 '材质:含量'
    assert prop_value_for('材质成分', 'x') == ['聚酯纤维:100']
    assert prop_value_for('上市年份季节', 'x') == [season_value()]
    assert prop_value_for('功能', '保暖加绒外套')[0] == '保暖'   # 标题关键词命中优先
    assert '居家' in prop_value_for('适用场景', '珊瑚绒睡衣家居服')
    assert prop_value_for('功能', '纯棉T恤')          # 推不出时仍有默认候选


if __name__ == '__main__':
    test_parse_gaps_known_fields()
    test_parse_gaps_no_false_positive()
    test_parse_gaps_inline_separate()
    test_image_only()
    test_sku_value_for()
    test_sku_value_for_options()
    test_sku_value_for_unknown_fields()
    test_prop_values()
    print('PASS: compliance filler pure logic')
