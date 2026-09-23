#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""任务完成度+上次执行时间统计（读 task-progress-config.json）"""
import json, os, time, collections
import pymysql

BASE = "/Users/qyk9527/ideaProject/spzx-parent/automation"
CFG = os.path.join(BASE, "sourcing/task-progress-config.json")


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def wc_lines(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return None


def status_dist(m):
    return collections.Counter(
        v.get("status", "?") if isinstance(v, dict) else "?" for v in m.values()
    )


def mtime_str(paths):
    ts = [os.path.getmtime(p) for p in paths if p and os.path.exists(p)]
    return time.strftime("%m-%d %H:%M", time.localtime(max(ts))) if ts else "—"


def mysql_rows(sql):
    try:
        conn = pymysql.connect(
            host="127.0.0.1", port=3306, user="root",
            password="root123456", database="db_spzx", charset="utf8mb4",
        )
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return None


def stat_task(t):
    tt, out = t["type"], {}
    files = [t.get("path"), t.get("progressFile"), t.get("logPath")]
    out["last"] = mtime_str([p for p in files if p])

    if tt == "json_progress":
        d = load_json(t["path"])
        if not d:
            return "无进度文件", None
        done = len(d.get("done", []) or [])
        processed, count = d.get("processed"), d.get("count")
        total = count if isinstance(count, int) and count else None
        pct = (done / total * 100) if total else (
            (processed / total * 100) if isinstance(processed, int) and total else None)
        return f"done {done}/count {count} (processed {processed})", pct

    if tt == "list_progress":
        d = load_json(t["path"])
        if not d:
            return "无进度文件", None
        done = len(d.get(t.get("doneKey", "done"), []))
        return f"done {done}", None

    if tt == "douyin_pipeline":
        pf = load_json(t["progressFile"])
        total = wc_lines(t.get("worklist") or t.get("dataFile"))
        saved = failed = 0
        if pf and "created" in pf:
            c = status_dist(pf["created"])
            saved = c.get("saved", 0)
            failed = sum(v for k, v in c.items() if k != "saved")
        if total:
            return f"saved {saved} + 失败 {failed} / 总 {total}", saved / total * 100
        return f"saved {saved} + 失败 {failed}", None

    if tt == "map_progress":
        d = load_json(t["path"])
        if not d:
            return "无进度文件", None
        mk = t.get("mapKey")
        m = d.get(mk) if mk else d
        if not isinstance(m, dict):
            return f"无 '{mk}' 键", None
        c = status_dist(m)
        saved = c.get("saved", 0) + c.get("fixed", 0) + c.get("submitted", 0)
        return f"{len(m)} 条 (saved {saved})", None

    if tt == "sourcing_progress":
        d = load_json(t["progressFile"]) or {}
        done, fail = len(d.get("done", [])), len(d.get("failed_kw", []))
        raw = wc_lines(t.get("rawFile"))
        return f"关键词 done {done} / 失败 {fail}，原始 {raw} 条", None

    if tt == "db_freight":
        d = load_json(t["progressFile"])
        return (f"done {len(d['done'])}", None) if d else ("无进度文件", None)

    if tt == "fanqie_publish":
        st = load_json(t["path"])
        if not st:
            return "无状态文件", None
        ch = st.get("chapters", {})
        c = collections.Counter(v.get("status", "?") for v in ch.values())
        out["last"] = st.get("updatedAt") or out["last"]
        return f"{len(ch)} 章 " + " ".join(f"{k} {v}" for k, v in c.most_common()), None

    if tt == "db_novel":
        rows = mysql_rows("SELECT status, COUNT(*) FROM novel_chapter GROUP BY status")
        if rows is None:
            return "MySQL 未连上", None
        m = {s: n for s, n in rows}
        name = {0: "草稿", 1: "待发", 2: "已发布"}
        total = sum(m.values())
        pub = m.get(2, 0)
        return (f"共 {total} 章：" + " ".join(f"{name[s]} {m[s]}" for s in sorted(m)),
                pub / total * 100 if total else None)

    if tt == "db_factory_grade":
        rows = mysql_rows("SELECT COUNT(*) FROM source_factory")
        return (f"厂家 {rows[0][0]} 家", None) if rows else ("MySQL 未连上", None)

    if tt == "db_inventory_alert":
        return f"计划: {t.get('schedule')}，下次 {t.get('nextRun')}", None

    return "—", None  # process_only 等


def main():
    cfg = json.load(open(CFG))
    print(f"{'key':<26}{'完成度':<44}{'上次执行':<12}pct")
    print("-" * 96)
    for t in cfg["tasks"]:
        summ, pct = stat_task(t)
        pct_s = f"{pct:.0f}%" if pct is not None else ""
        print(f"{t['key']:<26}{summ:<44}{stat_last(t):<12}{pct_s}")


def stat_last(t):
    if t["type"] == "fanqie_publish":
        st = load_json(t["path"])
        if st and st.get("updatedAt"):
            return st["updatedAt"][5:-3] if len(st["updatedAt"]) >= 16 else st["updatedAt"]
    files = [t.get("path"), t.get("progressFile"), t.get("logPath")]
    return mtime_str([p for p in files if p])


if __name__ == "__main__":
    main()
