#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clean_color_value 单元自检(纯函数, 无需浏览器). 跑法: venv/bin/python test_clean_color_value.py"""
from compliance_filler import clean_color_value

cases = [
    # (输入, 期望)
    ('XS 薄荷绿【细狗尖】', 'XS 薄荷绿-细狗尖'),          # 标准穿戴甲: 保留甲型防重名
    ('XS 枕边星屿【长椭圆】', 'XS 枕边星屿-长椭圆'),
    ('XS 珍妮【细狗尖】【950】', 'XS 珍妮-细狗尖-950'),    # 多段括号(ISV 08-29 实例格式)
    ('干净值', '干净值'),                                  # 无脏值原样
    ('a 【x】 b', 'a-x b'),                                # 括号前空白并入
    ('a【1】【2】', 'a-1-2'),                              # 连续括号
    ('【长椭圆】XS', '-长椭圆XS'),                         # 括号在开头
    ('', ''),                                              # 空串
    (None, ''),                                            # None 容错
    ('XS 黑粉千金 【细狗尖】 ', 'XS 黑粉千金-细狗尖'),     # 尾部空白
]
for inp, want in cases:
    got = clean_color_value(inp)
    assert got == want, f'clean_color_value({inp!r}) = {got!r}, want {want!r}'
# 重名防护依据: 清洗保留括号内文本 → 细狗尖/长椭圆 两甲型不冲突
a = clean_color_value('XS 黑粉千金【细狗尖】')
b = clean_color_value('XS 黑粉千金【长椭圆】')
assert a != b, f'甲型区分失效: {a!r} == {b!r}'
print(f'OK: {len(cases)} 用例 + 重名防护全过')
