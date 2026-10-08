#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日日程台账 —— 把「这天到底干了什么」写进后台「日程管理」。

为什么要有它：定时任务跑没跑、处理了多少行，事实散在 ingest_batch / sync_alert /
platform_product / novel_chapter 四张表加两个 git 仓库里；而「日程管理」页面自
2025-05-20 起只有一条手工记录，等于空着。这个脚本按天把六类事实汇成任务条目，
打开页面就能看，点详情有出处。

口径：
- 脚本写的条目 create_by=0；重跑同一天先删自己写的再写（幂等），人工在页面上加的任务不动。
- 完成与否由事实判定：定时任务有 failed/partial、告警还有未读 → 未完成；不粉饰。
- task_count / complete_count 每次按 status=0 的任务重算，与后端 Service 同一算法，进度条不撒谎。
- task_title 是 varchar(50)、remark 是 varchar(500)：超长只截标题，全文留在 remark。
- 数据源只覆盖「有台账/有时间列可追」的活儿。手工导入（对账 CSV、推广 CSV）不在
  ingest_batch 里，所以不进日程 —— 别把这里的条数当成当日全部工作量。

用法：
  daily_schedule.py                      # 今天
  daily_schedule.py --date 2026-10-06    # 指定一天
  daily_schedule.py --days 14            # 回补最近 14 天（含今天）
  daily_schedule.py --dry-run            # 只打印要写什么，不落库（也不写台账）
"""
import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "automation" / "sourcing"))
# 连接与跑批台账都复用 cron_batch：两处一份 SQL 迟早分叉，凭据也不该再抄第三份
from cron_batch import begin_batch, end_batch, connect  # noqa: E402

FRONTEND = os.environ.get("SPZX_FRONTEND_SRC", "/Users/qyk9527/webstormProject/spzx-admin")
DATASET = "daily_schedule"
AUTO_CREATE_BY = 0          # 标记「脚本写的」，与登录用户（id>=1）区分
TITLE_MAX = 50
REMARK_MAX = 500

# git 提交类型 → 页面上的中文标签；没写类型的（如「功能优化」）统一落「改动」
TYPE_LABEL = {
    "feat": "开发", "fix": "修复", "perf": "优化", "refactor": "重构",
    "docs": "文档", "test": "测试", "style": "样式", "build": "构建",
    "ci": "构建", "chore": "维护", "workflow": "维护", "types": "维护",
    "revert": "回退", "wip": "半成品",
}
REPOS = [("后端", str(REPO)), ("前端", FRONTEND)]


def cut(text, n):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n - 1] + "…"


def task(title, remark, complete, source):
    return {"title": cut(title, TITLE_MAX), "remark": cut(remark, REMARK_MAX),
            "is_complete": 1 if complete else 0, "source": source}


# ------------------------------------------------------------------ 六类事实

# GROUP_CONCAT 的分隔符：竖线之类会和报错文案自身打架；SEPARATOR 只接受字面量，
# 既不能写 char(1) 也不能当参数绑，所以拼进 SQL（常量，不含任何输入）
SEP = "\x01"
SEP_SQL = "'" + SEP + "'"


def batch_tasks(cur, date):
    """定时任务：按数据集汇总当天所有轮次，读数/落库条数都取台账原值"""
    cur.execute(
        "SELECT b.dataset, IFNULL(d.name, b.dataset) nm, COUNT(*) runs, "
        "SUM(b.status='success') ok, SUM(b.status='partial') part, SUM(b.status='failed') fail, "
        "SUM(b.rows_total) rt, SUM(b.rows_ok) ro, "
        "SUBSTRING_INDEX(GROUP_CONCAT(NULLIF(b.error,'') ORDER BY b.id SEPARATOR " + SEP_SQL
        + "), " + SEP_SQL + ", -1) err "
        "FROM ingest_batch b LEFT JOIN ingest_dataset d ON d.code = b.dataset "
        "WHERE DATE(b.started_at) = %s AND b.status <> 'running' "
        "GROUP BY b.dataset, nm ORDER BY rt DESC", (date,))
    tasks = []
    for code, name, runs, ok, part, fail, rt, ro, err in cur.fetchall():
        runs, ok, part, fail = (int(x or 0) for x in (runs, ok, part, fail))
        rt, ro = int(rt or 0), int(ro or 0)
        bad = part + fail
        detail = "%d 轮：成功 %d / 少一批 %d / 失败 %d · " % (runs, ok, part, fail)
        detail += "读 %d 行、落库 %d 行" % (rt, ro) if rt else "台账没记行数"
        if bad and err:
            detail += " · 最后报错：%s" % err
        tasks.append(task("定时任务：%s（%d 轮）" % (name, runs), detail, bad == 0, "batch:" + code))
    return tasks


def novel_tasks(cur, date):
    cur.execute("SELECT COUNT(*) FROM novel_chapter WHERE DATE(published_at) = %s", (date,))
    n = cur.fetchone()[0]
    if not n:
        return []
    return [task("番茄小说发布：%d 章" % n, "novel_chapter.published_at 当天落章", True, "novel")]


def product_tasks(cur, date):
    """在售商品登记：铺货批次写 platform_product，按平台拆开报"""
    cur.execute(
        "SELECT p.name, COUNT(*) n FROM platform_product b "
        "JOIN platform p ON p.code = b.platform_type WHERE DATE(b.create_time) = %s "
        "GROUP BY p.name ORDER BY n DESC", (date,))
    rows = cur.fetchall()
    if not rows:
        return []
    total = sum(int(r[1]) for r in rows)
    detail = " · ".join("%s %d 件" % (r[0], r[1]) for r in rows)
    return [task("商品登记：%d 件" % total, detail + "（在售快照，非当日新上架）", True, "product")]


def visual_tasks(cur, date):
    """主图质量分：分数由批量脚本或页面单张重算写入，update_time 是唯一线索"""
    cur.execute(
        "SELECT (SELECT COUNT(*) FROM product_media WHERE visual_score IS NOT NULL "
        "        AND DATE(update_time) = %s) pm, "
        "       (SELECT COUNT(*) FROM source_product WHERE visual_score IS NOT NULL "
        "        AND DATE(update_time) = %s) sp", (date, date))
    pm, sp = cur.fetchone()
    pm, sp = int(pm or 0), int(sp or 0)
    if not (pm or sp):
        return []
    return [task("主图质量分：本日打分 %d 张" % (pm + sp),
                "平台主图 %d 张 / 货源头图 %d 张" % (pm, sp), True, "visual")]


def alert_tasks(cur, date):
    cur.execute(
        "SELECT COUNT(*) n, SUM(status = 0) unread, "
        "SUBSTRING_INDEX(GROUP_CONCAT(CONCAT(alert_type, ' ', IFNULL(message, '')) "
        "ORDER BY id SEPARATOR " + SEP_SQL + "), " + SEP_SQL + ", -3) msgs "
        "FROM sync_alert WHERE DATE(create_time) = %s", (date,))
    n, unread, msgs = cur.fetchone()
    if not n:
        return []
    unread = int(unread or 0)
    detail = "未读 %d 条（已读/已自动解决 %d 条）" % (unread, int(n) - unread)
    if msgs:
        detail += " · 最近：%s" % msgs.replace("\x01", " | ")
    return [task("新增告警：%d 条" % n, detail, unread == 0, "alert")]


def collect_commits(since=None):
    """两个仓库的提交按日期分桶：一次扫全历史，回补多天不用反复起 git"""
    bucket = {}
    for label, path in REPOS:
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        r = subprocess.run(["git", "-C", path, "log", "--no-merges", "--date=short",
                            "--pretty=%ad%x1f%h%x1f%s"], capture_output=True, text=True)
        if r.returncode != 0:
            continue
        for line in r.stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 3:
                continue
            day, sha, subject = parts
            if since and day < since:
                continue
            bucket.setdefault((label, day), []).append((sha, subject))
    return bucket


def commit_tasks(date, bucket):
    tasks, plain = [], 0
    for label, _ in REPOS:
        rows = bucket.get((label, date), [])
        for sha, subject in rows:
            m = re.match(r"^\s*(\w+)(\([^)]*\))?!?:\s*(.*)$", subject, re.S)
            if m:
                kind = TYPE_LABEL.get(m.group(1).lower(), "改动")
                msg = m.group(3)
            else:
                kind, msg = ("改动", subject)
            if not msg or msg.strip().lower() in ("init", "update", "wip"):
                plain += 1
                continue
            tasks.append(task("[%s] %s：%s" % (label, kind, msg),
                              "%s %s · 原文：%s" % (label, sha, subject), True, "commit:" + sha))
    if plain:
        tasks.append(task("无描述提交：%d 条" % plain,
                          "subject 只有 init/update，看不出改了啥，去 git log 按日期翻", True, "commit:plain"))
    return tasks


# ------------------------------------------------------------------ 落库

def upsert_day(conn, date, user_id, tasks, dry):
    cur = conn.cursor()
    if dry:
        summary = "%d 项：%d 项已完成" % (len(tasks), sum(1 for t in tasks if t["is_complete"]))
        print("=== %s（dry-run，不写库）===" % date)
        for i, t in enumerate(tasks, 1):
            print("  %2d. [%s] %s | %s" % (i, "完成" if t["is_complete"] else "未完", t["title"], t["remark"]))
        if not tasks:
            print("   （当天没有可汇总的作业与提交）")
        return len(tasks)
    cur.execute("SELECT id FROM sys_user_schedule WHERE user_id=%s AND date_str=%s ORDER BY id LIMIT 1",
                (user_id, date))
    row = cur.fetchone()
    if row:
        schedule_id = int(row[0])
        cur.execute("UPDATE sys_user_schedule SET status=0, update_time=NOW() WHERE id=%s",
                    (schedule_id,))
    else:
        cur.execute(
            "INSERT INTO sys_user_schedule (user_id, date_str, task_count, complete_count, status, "
            "create_by, create_time, update_time) VALUES (%s,%s,0,0,0,%s,NOW(),NOW())",
            (user_id, date, user_id))
        schedule_id = int(cur.lastrowid)
    # 只清自己写的条目：create_by=0 是「脚本代笔」的标记，人工加的和 log_work 代记的
    # （create_by=-1）在页面上不会丢
    cur.execute("DELETE FROM sys_user_schedule_task WHERE schedule_id=%s AND create_by=%s",
                (schedule_id, AUTO_CREATE_BY))
    for i, t in enumerate(tasks, 1):
        cur.execute(
            "INSERT INTO sys_user_schedule_task (schedule_id, task_title, sort, complete_ratio, "
            "is_complete, status, create_by, create_time, update_time, remark) "
            "VALUES (%s,%s,%s,%s,%s,0,%s,NOW(),NOW(),%s)",
            (schedule_id, t["title"], i, 100 if t["is_complete"] else 0, t["is_complete"],
             AUTO_CREATE_BY, t["remark"]))
    # 进度条读的是父表这两列，算法与 SysUserScheduleTaskServiceImpl.updateCompleteValue 一致；
    # 注意是「全部 status=0 行」，含人工与 log_work 代记的条目 —— 故 remark 也必须用同一个全量
    # 口径重算，否则当天有手工条目时「N 项」与 task_count 对不上（见 work_log spec 4.4）
    cur.execute("SELECT COUNT(*), SUM(is_complete = 1) FROM sys_user_schedule_task "
                "WHERE schedule_id=%s AND status=0", (schedule_id))
    total, done = cur.fetchone()
    total, done = int(total or 0), int(done or 0)
    cur.execute("UPDATE sys_user_schedule SET task_count=%s, complete_count=%s, remark=%s, "
                "update_time=NOW() WHERE id=%s",
                (total, done, "%d 项：%d 项已完成" % (total, done), schedule_id))
    cur.close()
    conn.commit()
    return len(tasks)


def main():
    ap = argparse.ArgumentParser(description="每日日程台账")
    ap.add_argument("--date", help="只处理这一天 YYYY-MM-DD")
    ap.add_argument("--days", type=int, default=1, help="回补最近 N 天（含今天）")
    ap.add_argument("--user", type=int, default=1, help="日程归属用户 id，默认 1=admin")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = dt.date.today()
    if args.date:
        days = [dt.datetime.strptime(args.date, "%Y-%m-%d").date()]
    else:
        days = [today - dt.timedelta(days=n) for n in range(args.days - 1, -1, -1)]
    dates = [d.strftime("%Y-%m-%d") for d in days]

    bucket = collect_commits(since=min(dates))
    conn = connect()
    if conn is None:
        print("数据库连不上，本次不写日程（台账也不记）", file=sys.stderr)
        return 1
    batch_id = None if args.dry_run else begin_batch(DATASET, channel="derived",
                                                     biz_from=dates[0], biz_to=dates[-1])
    written = 0
    errors = []
    try:
        cur = conn.cursor()
        for date in dates:
            tasks = []
            for fn in (batch_tasks, novel_tasks, product_tasks, visual_tasks, alert_tasks):
                try:
                    tasks += fn(cur, date)
                except Exception as e:
                    errors.append("%s %s: %s" % (date, fn.__name__, str(e)[:200]))
            tasks += commit_tasks(date, bucket)
            if not tasks:
                tasks = [task("当天没有可汇总的作业", "无跑批台账、无质量分写入、无提交", True, "empty")]
            written += upsert_day(conn, date, args.user, tasks, args.dry_run)
        cur.close()
    except Exception as e:
        errors.append(str(e)[:200])
        raise
    finally:
        if not args.dry_run:
            status = "success" if not errors else ("partial" if written else "failed")
            end_batch(batch_id, status, rows_total=written, rows_ok=written,
                      error=" · ".join(errors)[:900] if errors else None)
    print("日程写入完成：%d 天 / %d 条任务%s" % (len(dates), written, "（dry-run 未落库）" if args.dry_run else ""))
    if errors:
        print("有数据源取数失败：%s" % " · ".join(errors), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
