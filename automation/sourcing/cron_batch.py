#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cron 跑批台账：每次定时执行在 ingest_batch 留一行结构化事实。

为什么不用 /tmp 日志：看板上定时卡的"最近日志"读的就是 /tmp/*.log，而 macOS 重启会清
/tmp（2026-09-29 09:04 重启后这些文件全部消失），跑批历史随之蒸发；库里这行活得过重启。

用法:
  ID=$(cron_batch.py begin --dataset source_sku)
  <跑真正的采集脚本>
  cron_batch.py end --id "$ID" --status success --rows-total 1200

begin 失败时输出空串，end 收到空 id 直接 no-op；退出码恒 0——台账写不进不能把 cron 打挂。

crontab 里直接调 python 的作业（没有 bash 包装层）import begin_batch/end_batch 用同一套写库逻辑，
两套调用路径共用一份 SQL，不会出现包装器改了、脚本内埋点没跟着改。
"""
import argparse
import hashlib
import os
import sys
import time

import pymysql
from shop_ref import default_shop_id

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
TERMINAL = ("success", "partial", "failed")
# 超过这个小时数还挂在 running 就是没人收尾（进程被 kill / 机器关机），补成 failed 说明真相
STALE_RUNNING_HOURS = 12


def log(msg):
    print(f"[{time.strftime('%F %T')}] [cron_batch] {msg}", file=sys.stderr, flush=True)


def connect():
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        log(f"连接数据库失败，本次台账不记录: {e}")
        return None


def begin_batch(dataset, channel="browser", platform=None, biz_from=None, biz_to=None):
    """开一条 running 批次，返回自增 id；写不进返回 None（调用方据此走无台账路径）。"""
    conn = connect()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        started = int(time.time())
        fingerprint = hashlib.md5(
            f"{dataset}:{started}:{os.getpid()}".encode()).hexdigest()
        shop_id = default_shop_id(cur, platform) if platform else None
        # 上一轮没收尾的 running 行（脚本被 kill、机器直接关机）补成 failed，
        # 否则台账会一直挂着一条"正在跑"的假状态
        cur.execute(
            "UPDATE ingest_batch SET status='failed', finished_at=NOW(), "
            "error=CONCAT(COALESCE(error,''), '未正常收尾：超过 ', %s, ' 小时仍是 running') "
            "WHERE dataset=%s AND status='running' "
            "AND started_at < DATE_SUB(NOW(), INTERVAL %s HOUR)",
            (STALE_RUNNING_HOURS, dataset, STALE_RUNNING_HOURS))
        swept = cur.rowcount
        cur.execute(
            "INSERT INTO ingest_batch (platform_code, shop_id, dataset, channel, biz_from, "
            "biz_to, status, fingerprint, started_at) VALUES (%s,%s,%s,%s,%s,%s,'running',%s,NOW())",
            (platform, shop_id, dataset, channel, biz_from, biz_to, fingerprint))
        conn.commit()
        batch_id = cur.lastrowid
        if swept:
            log(f"顺带把 {swept} 条未收尾的 running 补成 failed")
        log(f"begin dataset={dataset} id={batch_id} shop_id={shop_id}")
        return int(batch_id)
    except Exception as e:
        log(f"begin 失败，本次台账不记录: {e}")
        return None
    finally:
        conn.close()


def end_batch(batch_id, status, rows_total=0, rows_ok=0, rows_dup=0,
              rows_invalid=0, error=None):
    if not batch_id:
        log("id 为空（begin 未成功），end 跳过")
        return
    if status not in TERMINAL:
        log(f"非法 status={status}，只接受 {TERMINAL}，end 跳过")
        return
    # 与 cron_alert 同理：LANG 为空时 shell 可能把 error 文案里的多字节字符切坏，
    # 非法 UTF-8 会让这条 UPDATE 整体失败，批次就永远挂在 running
    if error:
        error = error.encode("utf-8", "replace").decode("utf-8")[:1000]
    try:
        batch_id = int(batch_id)
    except (TypeError, ValueError):
        log(f"非法批次 id={batch_id!r}，end 跳过")
        return
    conn = connect()
    if conn is None:
        return
    try:
        cur = conn.cursor()
        # LANG 为空时 shell 可能把变量后的多字节字符切坏半个字节，非法 UTF-8 会让这条
        # UPDATE 整体失败、批次永远挂在 running——替换坏字节，记录必须落得下
        safe_error = error.encode("utf-8", "replace").decode("utf-8")[:1000] if error else None
        cur.execute(
            "UPDATE ingest_batch SET status=%s, rows_total=%s, rows_ok=%s, rows_dup=%s, "
            "rows_invalid=%s, error=%s, finished_at=NOW() WHERE id=%s",
            (status, rows_total, rows_ok, rows_dup, rows_invalid,
             safe_error, batch_id))
        conn.commit()
        if cur.rowcount == 0:
            log(f"end 未命中批次 id={batch_id}")
        else:
            log(f"end id={batch_id} status={status} rows={rows_total}")
    except Exception as e:
        log(f"end 失败: {e}")
    finally:
        conn.close()


def begin(args):
    batch_id = begin_batch(args.dataset, channel=args.channel, platform=args.platform,
                           biz_from=args.biz_from, biz_to=args.biz_to)
    return str(batch_id) if batch_id else ""


def end(args):
    end_batch(args.id, args.status, rows_total=args.rows_total, rows_ok=args.rows_ok,
              rows_dup=args.rows_dup, rows_invalid=args.rows_invalid, error=args.error)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("begin")
    b.add_argument("--dataset", required=True, help="ingest_dataset.code")
    b.add_argument("--channel", default="browser", help="api|browser|export")
    b.add_argument("--platform", type=int, default=None,
                   help="平台 code；1688 上游类任务不传，归属留空")
    b.add_argument("--biz-from", default=None)
    b.add_argument("--biz-to", default=None)

    e = sub.add_parser("end")
    e.add_argument("--id", default="")
    e.add_argument("--status", required=True)
    e.add_argument("--rows-total", type=int, default=0)
    e.add_argument("--rows-ok", type=int, default=0)
    e.add_argument("--rows-dup", type=int, default=0)
    e.add_argument("--rows-invalid", type=int, default=0)
    e.add_argument("--error", default=None)

    args = parser.parse_args()
    if args.cmd == "begin":
        sys.stdout.write(begin(args))
    else:
        end(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # argparse 之外的任何异常都不该让 cron 非零退出
        log(f"未预期异常: {exc}")
        sys.exit(0)
