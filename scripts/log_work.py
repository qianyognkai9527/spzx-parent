#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作留痕 —— 每完成一件活就把它写进当天「日程管理」。

为什么要有它：淘宝归类 v2 / 品牌标题 / PDD 铺货 / 1688 选品 / AI 选词 / 图片下载等
手做的自动化活，**没有 git commit 就不进**每天 23:30 由 daily_schedule.py 汇总的日程，
事后无从按模块排查漏做。这个脚本让 AI（或人）在活收尾时立即记一条，带数据进度、带模块。

与 daily_schedule.py 的分工与冲突隔离：
- 本脚本写的行 create_by = -1（哨兵「AI/手工代记」）；daily_schedule.py 每天 23:30 只
  `DELETE ... WHERE create_by=0`（自动台账），**删不到这里**。页面人工加的仍是用户 id(>=1)。
- sort 用 1000+ 段，排在自动条目（1..N）之后。
- 不写 ingest_batch、不注册 ingest_dataset：它不是定时作业，免得污染「应跑」口径。

用法：
  # 长任务告一段落：文件自动解析进度 + 合并当天同模块同标题（不堆行）
  log_work.py --module 淘宝归类 --title "归类v2 第N轮" \\
    --progress-file automation/sourcing/shop_cat_v2_progress.json --merge

  # 零散小活：手填进度，直接追加（保留时间线）
  log_work.py --module 对账 --title "支付宝账单导入" --progress "33 行，0 失败"

  # 未完成、还差一截
  log_work.py --module PDD铺货 --title "穿戴甲首轮" --incomplete --ratio 40

  log_work.py ... --dry-run     # 只打印将写什么，不落库
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "automation" / "sourcing"))
# 连接复用 cron_batch：凭据只此一份，别再抄第三份 DB_CONFIG
from cron_batch import connect  # noqa: E402

AI_CREATE_BY = -1          # 哨兵：AI/手工代记，与自动台账(0)、登录用户(>=1)都不同
SORT_BASE = 1000           # 手工条目排在自动条目(1..N)之后
TITLE_MAX = 50
REMARK_MAX = 500
DEFAULT_USER = 1           # admin


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def cut(text, n):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n - 1] + "…"


# ------------------------------------------------------------------ 进度解析

def parse_progress_file(path):
    """进度文件 → 概览串。

    实测三份目标文件都是顶层 dict，我把「值是 list 或 dict」的键取 len()，
    例如 shop_cat_v2_progress.json → {done:[…], skipped:[…], noprice:[],
    failed:{…}, sizegap:{}} 得 "done 1464 / skipped 1339 / failed 1079…"。
    解析不出（文件缺失/非预期结构）不报错退出，回 None 并在 stderr 提示。
    """
    p = pathlib.Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log(f"进度文件不存在，跳过解析：{p}")
        return None
    except Exception as e:
        log(f"进度文件解析失败（{p}）：{str(e)[:200]}")
        return None
    if not isinstance(data, dict):
        log(f"进度文件顶层不是 dict，跳过解析：{p}")
        return None
    counts = [(k, len(v)) for k, v in data.items() if isinstance(v, (list, dict))]
    if not counts:
        log(f"进度文件里没有 list/dict 字段，跳过解析：{p}")
        return None
    # 按数量降序：done 常年最大，读起来先看大头
    counts.sort(key=lambda kv: kv[1], reverse=True)
    return " / ".join(f"{k} {n}" for k, n in counts)


def build_remark(progress_file, progress_text, extra_remark):
    parts = []
    if progress_file:
        got = parse_progress_file(progress_file)
        if got:
            parts.append(got)
    if progress_text:
        parts.append(progress_text.strip())
    if extra_remark:
        parts.append(extra_remark.strip())
    return cut(" ".join(p for p in parts if p), REMARK_MAX)


# ------------------------------------------------------------------ 落库

def find_schedule(cur, user_id, date):
    cur.execute("SELECT id FROM sys_user_schedule WHERE user_id=%s AND date_str=%s "
                "ORDER BY id LIMIT 1", (user_id, date))
    row = cur.fetchone()
    return int(row[0]) if row else None


def ensure_schedule(cur, user_id, date):
    schedule_id = find_schedule(cur, user_id, date)
    if schedule_id is not None:
        cur.execute("UPDATE sys_user_schedule SET status=0, update_time=NOW() WHERE id=%s",
                    (schedule_id,))
        return schedule_id
    cur.execute("INSERT INTO sys_user_schedule (user_id, date_str, task_count, complete_count, "
                "status, create_by, create_time, update_time) VALUES (%s,%s,0,0,0,%s,NOW(),NOW())",
                (user_id, date, user_id))
    return int(cur.lastrowid)


def recompute_parent(cur, schedule_id):
    """父表 task_count/complete_count/remark 全量重算。

    算法与 daily_schedule.py、Java SysUserScheduleTaskServiceImpl.updateCompleteValue 一致；
    remark 也按全量 status=0 行生成，否则当天有手工条目时「N 项」与 task_count 对不上。
    """
    cur.execute("SELECT COUNT(*), SUM(is_complete = 1) FROM sys_user_schedule_task "
                "WHERE schedule_id=%s AND status=0", (schedule_id,))
    total, done = cur.fetchone()
    total, done = int(total or 0), int(done or 0)
    cur.execute("UPDATE sys_user_schedule SET task_count=%s, complete_count=%s, remark=%s, "
                "update_time=NOW() WHERE id=%s",
                (total, done, "%d 项：%d 项已完成" % (total, done), schedule_id))
    return total, done


def write_one(conn, args, date, title, module, remark, is_complete, complete_ratio, dry):
    cur = conn.cursor()
    schedule_id = find_schedule(cur, args.user, date)
    action = "append"
    task_id = None
    sort = None
    if args.merge and schedule_id is not None:
        cur.execute(
            "SELECT id FROM sys_user_schedule_task "
            "WHERE schedule_id=%s AND create_by=%s AND module <=> %s AND task_title=%s "
            "AND status=0 LIMIT 1",
            (schedule_id, AI_CREATE_BY, module, title))
        row = cur.fetchone()
        if row:
            task_id = int(row[0])
            action = "merge"
    if dry:
        print("=== %s（dry-run，不写库）===" % date)
        print("  动作：%s" % ("合并更新已有行" if action == "merge" else "新增一行（追加）"))
        print("  模块：%s" % (module or "（空）"))
        print("  标题：%s" % title)
        print("  完成：%s（%d%%）" % ("已完成" if is_complete else "未完成", complete_ratio))
        print("  备注：%s" % remark)
        return action, task_id, sort
    schedule_id = ensure_schedule(cur, args.user, date)
    if action == "merge":
        cur.execute("UPDATE sys_user_schedule_task SET task_title=%s, module=%s, complete_ratio=%s, "
                    "is_complete=%s, remark=%s, update_time=NOW() WHERE id=%s",
                    (title, module, complete_ratio, is_complete, remark, task_id))
    else:
        cur.execute("SELECT COUNT(*) FROM sys_user_schedule_task WHERE schedule_id=%s AND create_by=%s",
                    (schedule_id, AI_CREATE_BY))
        sort = SORT_BASE + int(cur.fetchone()[0])
        cur.execute(
            "INSERT INTO sys_user_schedule_task (schedule_id, task_title, module, sort, complete_ratio, "
            "is_complete, status, create_by, create_time, update_time, remark) "
            "VALUES (%s,%s,%s,%s,%s,%s,0,%s,NOW(),NOW(),%s)",
            (schedule_id, title, module, sort, complete_ratio, is_complete, AI_CREATE_BY, remark))
        task_id = int(cur.lastrowid)
    total, done = recompute_parent(cur, schedule_id)
    cur.close()
    conn.commit()
    print("已记入 %s 日程：%s | %s | %s（%s；父表 %d 项/%d 完成）"
          % (date, module or "（空模块）", title, remark,
             "合并更新" if action == "merge" else "新增", total, done))
    return action, task_id, sort


def main():
    ap = argparse.ArgumentParser(description="工作留痕：把一件活写进当天日程")
    ap.add_argument("--module", required=True, help="任务模块（自由文本，建议中文名）")
    ap.add_argument("--title", required=True, help="任务标题")
    ap.add_argument("--remark", default=None, help="补充说明（拼在进度串之后）")
    ap.add_argument("--progress-file", default=None, help="进度 JSON 文件，自动解析各字段条数")
    ap.add_argument("--progress", default=None, help="手填进度文本")
    ap.add_argument("--merge", action="store_true",
                    help="按「同一天 + 模块 + 标题」原地更新，不新增行")
    ap.add_argument("--incomplete", action="store_true", help="标记未完成")
    ap.add_argument("--ratio", type=int, default=0, help="未完成时的完成百分比 0..100")
    ap.add_argument("--date", default=None, help="归属日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--user", type=int, default=DEFAULT_USER, help="日程归属用户 id，默认 1=admin")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.date:
        try:
            date = dt.datetime.strptime(args.date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            log("--date 必须形如 YYYY-MM-DD")
            return 2
    else:
        date = dt.date.today().strftime("%Y-%m-%d")

    ratio = 0 if not (0 <= args.ratio <= 100) else args.ratio
    if args.ratio != ratio:
        log("--ratio 超出 0..100，已按 %d 处理" % ratio)
    is_complete = 0 if args.incomplete else 1
    complete_ratio = ratio if args.incomplete else 100

    title = cut(args.title, TITLE_MAX)
    module = (args.module or "").strip() or None
    remark = build_remark(args.progress_file, args.progress, args.remark)

    # dry-run 也连库：--merge 需要查是否命中已有行；连不上就退化成 append 预览
    conn = connect()
    if conn is None:
        if args.dry_run:
            log("数据库连不上，--merge 命中判断不可用，按新增预览")
            print("=== %s（dry-run，不写库・未连库）===" % date)
            print("  模块：%s | 标题：%s | 完成：%s | 备注：%s"
                  % (module or "（空）", title, "已完成" if is_complete else "未完成", remark))
            return 1
        log("数据库连不上，本次不记")
        return 1

    try:
        write_one(conn, args, date, title, module, remark, is_complete, complete_ratio, args.dry_run)
    except Exception as e:
        log("写库失败：%s" % str(e)[:300])
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
