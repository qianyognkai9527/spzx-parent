#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""淘宝品牌/标题批处理的纯逻辑: 瑰若前缀规整、目标去重、进度合并。
浏览器无关, 单测直跑。"""
PREFIX = '瑰若'
TITLE_MAX = 30  # Phase 0 探路确认淘宝标题真实上限, 不符则改这里


def ensure_guiruo_prefix(title, prefix=PREFIX, max_len=TITLE_MAX):
    """保证标题前两个字是 prefix: 去掉标题里所有 prefix 后前置一个, 再按 max_len 截断。"""
    t = (title or '').strip()
    t = t.replace(prefix, '')
    out = prefix + t
    return out[:max_len]


def dedup_targets(rows):
    """按 itemId 去重; 同一 itemId 同时出现在两池时 onsale 优先。"""
    seen = {}
    for r in rows:
        iid = str(r.get('itemId') or '')
        if not iid:
            continue
        cur = seen.get(iid)
        pool = r.get('pool', 'warehouse')
        if cur is None or (pool == 'onsale' and cur.get('pool') != 'onsale'):
            seen[iid] = {'itemId': iid, 'title': r.get('title', ''), 'pool': pool}
    return list(seen.values())


def merge_progress(disk, prog):
    """磁盘合并: done/skipped 并集, failed 覆盖后剔除已 done/skipped(防旧档复活)。"""
    merged = {
        'done': sorted(set(disk.get('done', [])) | set(prog.get('done', []))),
        'skipped': sorted(set(disk.get('skipped', [])) | set(prog.get('skipped', []))),
        'failed': {**disk.get('failed', {}), **prog.get('failed', {})},
    }
    for k in list(merged['failed']):
        if k in merged['done'] or k in merged['skipped']:
            del merged['failed'][k]
    return merged
