#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把技能目录里的合规词表同步进仓（compliance_rules.json）。

跑法: automation/venv/bin/python sync_compliance_rules.py [--check] [--from <path>]
  --check  只比对不写，词表有漂移时退出码 1（可以当检查用）

为什么进仓而不是运行时读技能目录：技能装在用户本地，路径一挪、机器一换就找不到，
而闸门的设计是"规则库缺失就报错、绝不静默放行"。进仓 + 记录来源与同步时间，
既能独立跑，又留了"这份是哪天从哪抄的"的线索。
"""
import argparse
import json
import os
import time

import pdd_compliance as G

DEFAULT_SKILL = os.path.expanduser(
    "~/.qoder-cn/skills/global-ecommerce-intelligence/references/scripts/compliance-rules.json")
CATEGORIES = ("absolute_terms", "medical_terms", "price_terms", "trademark_hint")


def load_skill_rules(path):
    """读技能侧规则库。缺失必须抛错 —— 静默返回空表会把仓内规则覆盖成空，闸门就此失效。"""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"技能侧合规规则库不存在：{path}。技能未安装或已改名时不要同步，"
            "仓内 compliance_rules.json 保持原样即可。")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    rules = doc.get("rules")
    if not isinstance(rules, dict) or not any(rules.get(c) for c in CATEGORIES):
        raise ValueError(f"技能规则库 {path} 里没有可用的 rules 词表，拒绝同步。")
    return rules, doc.get("version") or "unknown"


def diff_rules(old, new):
    """按类别算新增/删除。changed 给 --check 用。"""
    added, removed = {}, {}
    for cat in set(old) | set(new):
        o, n = set(old.get(cat) or []), set(new.get(cat) or [])
        if o != n:
            if n - o:
                added[cat] = sorted(n - o)
            if o - n:
                removed[cat] = sorted(o - n)
    return {"added": added, "removed": removed, "changed": bool(added or removed)}


def build_doc(rules, source, version):
    """平台红线词表按平台分档，counts 里摊平成 platform_red_line.<platform> 便于看漂移。"""
    counts = {c: len(rules.get(c) or []) for c in CATEGORIES}
    for plat, words in (rules.get("platform_red_line") or {}).items():
        counts[f"platform_red_line.{plat}"] = len(words or [])
    return {"_meta": {"source": source, "skill_version": version,
                      "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "note": "从技能目录同步进仓的副本；改这个文件等于偏离上游，"
                              "要长期保留的本地词请放 pdd_config.BRAND_WORDS",
                      "counts": counts},
            "rules": rules}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对漂移, 不写文件")
    ap.add_argument("--from", dest="src", default=DEFAULT_SKILL)
    ap.add_argument("--out", default=G.RULES)
    args = ap.parse_args()

    rules, version = load_skill_rules(args.src)
    old = {}
    if os.path.exists(args.out):
        try:
            old = json.load(open(args.out, encoding="utf-8")).get("rules") or {}
        except Exception:
            old = {}
    d = diff_rules(old, rules)
    print(f"技能版本 {version} | 词表 {sum(len(v) for v in rules.values() if isinstance(v, list))} 条"
          f"（红线词按平台分档另计）")
    if d["changed"]:
        for cat, ws in sorted(d["added"].items()):
            print(f"  + {cat}: {len(ws)} 条 {ws[:6]}")
        for cat, ws in sorted(d["removed"].items()):
            print(f"  - {cat}: {len(ws)} 条 {ws[:6]}")
    else:
        print("  与仓内规则库一致，无漂移")
    if args.check:
        raise SystemExit(1 if d["changed"] else 0)
    doc = build_doc(rules, args.src, version)
    tmp = args.out + ".tmp"
    json.dump(doc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)
    print(f"WROTE {args.out}")


if __name__ == "__main__":
    main()
