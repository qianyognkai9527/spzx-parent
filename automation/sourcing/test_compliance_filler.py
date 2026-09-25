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


if __name__ == '__main__':
    test_parse_gaps_known_fields()
    test_parse_gaps_no_false_positive()
    test_parse_gaps_inline_separate()
    test_image_only()
    print('PASS: compliance filler pure logic')
