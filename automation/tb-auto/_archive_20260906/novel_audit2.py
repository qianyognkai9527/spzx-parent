#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮审计: 名词一致性(编辑距离1变体)/叠字异常/半角字符/引号配平。
只打印统计与短语级上下文, 不输出连续正文。"""
import re
from collections import Counter, defaultdict

import pymysql

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
MIN_CH, MAX_CH = 51, 200

# 叠字异常: 这些字叠用基本必错
DUP_CHARS = "的地得了是在和与并或把被将让从向也很才就是不"

CN = re.compile(r"[\u4e00-\u9fff]")


def ctx(content, pos, width=8):
    s = max(0, pos - width)
    return content[s:pos + width + 2].replace("\n", "⏎")


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        "SELECT chapter_num, title, content FROM novel_chapter "
        "WHERE novel_id=1 AND is_deleted=0 AND chapter_num BETWEEN %s AND %s",
        (MIN_CH, MAX_CH))
    rows = cur.fetchall()
    cur.close(); conn.close()

    issues = []

    # 1) 叠字异常 (xx 同字相邻)
    for num, title, content in rows:
        for m in re.finditer(r"(.)\1", content):
            c = m.group(1)
            if c in DUP_CHARS:
                issues.append(("叠字", f"{c}{c}", num, ctx(content, m.start())))

    # 2) 半角字符: 字母数字/半角标点 混入中文正文
    for num, title, content in rows:
        for m in re.finditer(r"[,;:?!]", content):
            issues.append(("半角标点", m.group(), num, ctx(content, m.start())))
        for m in re.finditer(r'[A-Za-z0-9]{2,}', content):
            issues.append(("西文串", m.group(), num, ctx(content, m.start())))
        if content.count('“') != content.count('”'):
            issues.append(("引号不配平",
                           f"开{content.count('“')}闭{content.count('”')}",
                           num, "—"))
        t = title or ""
        for m in re.finditer(r"[,;:?!.\s]", t):
            issues.append(("标题异常", repr(m.group()), num, t))

    # 3) 名词一致性: 高频bigram vs 低频编辑距离1变体(反向生成邻居, 避免 O(n²))
    bigrams = Counter()
    where = defaultdict(set)
    for num, title, content in rows:
        for seg in content.split("\n"):
            cn = "".join(re.findall(r"[\u4e00-\u9fff]", seg))
            for i in range(len(cn) - 1):
                bg = cn[i:i + 2]
                bigrams[bg] += 1
                where[bg].add(num)

    common = {bg for bg, c in bigrams.items() if c >= 8}
    charset = {ch for bg in common for ch in bg}
    rare_variants = []
    for other, cnt in bigrams.items():
        if cnt > 3 or other in common:
            continue
        for i in range(2):
            for ch in charset:
                bg = other[:i] + ch + other[i + 1:]
                if bg in common:
                    rare_variants.append((bg, bigrams[bg], other, cnt,
                                          sorted(where[other])[:5]))
                    break
    print(f"扫描 {len(rows)} 章, 问题合计 {len(issues)} 处 + 名词变体 {len(rare_variants)} 组\n")

    agg = Counter((t, v) for t, v, n, c in issues)
    for (t, v), c in agg.most_common(60):
        exs = [(n, ct) for tt, vv, n, ct in issues if tt == t and vv == v][:3]
        print(f"[{t}] {v!r} ×{c}  例: {exs}")
    print("\n--- 名词变体(低频疑似错写) ---")
    for bg, c1, other, c2, chs in sorted(rare_variants, key=lambda x: x[3]):
        print(f"高频 {bg}×{c1}  vs  低频 {other}×{c2}  章节{chs}")


if __name__ == "__main__":
    main()
