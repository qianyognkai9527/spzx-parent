#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成店铺中分类计划: 读 in_stock 标题 -> 按规则归类 -> shop_cat_plan.json
规则(已与用户确认):
  1. 美甲: 穿戴甲/美甲/甲片/光疗/甲油/美睫/假指甲
  2. 牛仔短裤: 牛仔短裤
  3. 秋冬款(优先于家居服): 秋冬/加厚/保暖/加绒/毛绒/毛衣/针织/外套/大衣/开衫/卫衣/棉服/羽绒/皮草/马甲/打底衫/羊绒/呢子
  4. 半身裙: 半身裙
  5. 连衣裙: 连衣裙
  6. 长裤(排除套装词): 长裤/阔腿/直筒裤/牛仔裤/打底裤/休闲裤/喇叭裤/束脚裤/工装裤/西装裤, 且不含套装词
  7. 家居服/睡衣: 睡裙/睡衣/家居服/睡袍/睡裤/家居套装/吊带裙/胸垫/内衣/外袍/丝绒/缎面/冰丝
  8. other: 其余(含垃圾标题)
用法: python build_shop_cat_plan.py [--input taobao_in_stock_current.jsonl] [--show]
"""
import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

SET_SUITE = ['睡裙', '睡衣', '家居服', '睡袍', '睡裤', '家居套装', '吊带裙', '胸垫', '内衣', '外袍', '丝绒', '缎面', '冰丝', '套装']
RULES = [
    ('美甲', ['穿戴甲', '美甲', '甲片', '光疗', '甲油', '美睫', '假指甲'], None),
    ('牛仔短裤', ['牛仔短裤'], None),
    ('秋冬款', ['秋冬', '加厚', '保暖', '加绒', '毛绒', '毛衣', '针织', '外套', '大衣', '开衫', '卫衣', '棉服', '羽绒', '皮草', '马甲', '打底衫', '羊绒', '呢子'], None),
    ('半身裙', ['半身裙'], None),
    ('连衣裙', ['连衣裙'], None),
    ('长裤', ['长裤', '阔腿', '直筒裤', '牛仔裤', '打底裤', '休闲裤', '喇叭裤', '束脚裤', '工装裤', '西装裤'], SET_SUITE),
    ('家居服/睡衣', ['睡裙', '睡衣', '家居服', '睡袍', '睡裤', '家居套装', '吊带裙', '胸垫', '内衣', '外袍', '丝绒', '缎面', '冰丝'], None),
]
CATS = ['家居服/睡衣', '牛仔短裤', '秋冬款', '连衣裙', '长裤', '半身裙', '美甲', 'other']


def classify(title):
    for cat, kws, exclude in RULES:
        if exclude and any(k in title for k in exclude):
            continue
        if any(k in title for k in kws):
            return cat
    return 'other'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default=os.path.join(BASE, 'taobao_in_stock_current.jsonl'))
    ap.add_argument('--output', default=os.path.join(BASE, 'shop_cat_plan.json'))
    ap.add_argument('--show', action='store_true')
    args = ap.parse_args()

    rows = []
    for line in open(args.input, encoding='utf-8'):
        line = line.strip()
        if line:
            r = json.loads(line)
            rows.append((r['itemId'], r.get('title', '')))

    plan = []
    for iid, title in rows:
        plan.append({'itemId': iid, 'title': title, 'category': classify(title)})

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)

    from collections import Counter
    buckets = Counter(p['category'] for p in plan)
    print(f'共 {len(plan)} 个商品')
    for c in CATS:
        print(f'  {c:<8} {buckets[c]:>5}')
    if args.show:
        samples = {}
        for p in plan:
            samples.setdefault(p['category'], []).append(p)
        for c in CATS:
            print(f'=== {c} ({len(samples.get(c, []))}) ===')
            for p in samples.get(c, [])[:6]:
                print('   ', p['title'][:48])
    print(f'-> {args.output}')


if __name__ == '__main__':
    main()
