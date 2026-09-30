#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定时任务跳过即告警：cron 守卫判定"本轮不跑"或本轮跑挂时写一条 sync_alert。

只有脚本自己知道"今天没跑成"；后端的新鲜度巡检最快也要一小时后才从库里判出来，
这段静默窗口靠本脚本补齐。纯 DB 写入，不需要 Chrome。

用法: cron_alert.py --key sycm_snapshot --msg "Chrome 9222 不在线, 每日快照未落库" [--platform 1]
      --type cron_skipped(默认，守卫主动跳过) | cron_failed(作业自己跑挂了)
去重: 同一 (type, key) 存在未读提醒时不再重复插入 —— 运营读完之后下一次跳过才会再报。
退出码恒为 0：告警写失败不能把整条 cron 链拖成失败。
"""
import argparse
import sys
from datetime import datetime

import pymysql
from shop_ref import default_shop_id

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "root123456", "database": "db_spzx", "charset": "utf8mb4",
}
ALERT_TYPE = "cron_skipped"
FAILED_TYPE = "cron_failed"


def log(msg):
    print(f"[{datetime.now().strftime('%F %T')}] [cron_alert] {msg}", flush=True)


def _utf8_safe(text, limit):
    """LANG 为空时 bash 会把变量名后的多字节字符吞掉半个字节（`rc=$arc（x` 实证），
    留下非法 UTF-8 让 pymysql 编码失败——那样整条告警会静默消失。宁可消息里出现替代符，
    也要把记录留下来。"""
    if not text:
        return None
    return text.encode("utf-8", "replace").decode("utf-8")[:limit]


def write_alert(key, msg, platform=None, alert_type=ALERT_TYPE):
    """写一条运维提醒；返回 True 表示本轮确实新插入。任何异常都吞掉——告警不能拖垮作业。"""
    key = _utf8_safe(key, 100)
    msg = _utf8_safe(msg, 500)
    try:
        conn = pymysql.connect(**DB_CONFIG)
    except Exception as e:
        log(f"连接数据库失败, 本次告警丢弃: {e}")
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM sync_alert WHERE alert_type=%s AND old_value=%s AND status=0 LIMIT 1",
            (alert_type, key))
        if cur.fetchone():
            log(f"{key} 已有未读提醒, 不重复插入")
            return False
        shop_id = default_shop_id(cur, platform) if platform else None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO sync_alert (alert_type, shop_id, old_value, message, status, create_time) "
            "VALUES (%s,%s,%s,%s,0,%s)",
            (alert_type, shop_id, key, msg, now))
        conn.commit()
        log(f"已写入提醒 type={alert_type} key={key} shop_id={shop_id}")
        return True
    except Exception as e:
        log(f"写入提醒失败, 跳过告警未记录: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True, help="任务标识, 用于去重与溯源")
    parser.add_argument("--msg", required=True, help="跳过原因与影响")
    parser.add_argument("--type", default=ALERT_TYPE, choices=[ALERT_TYPE, FAILED_TYPE],
                        help="cron_skipped=守卫主动跳过; cron_failed=作业跑挂")
    parser.add_argument("--platform", type=int, default=None,
                        help="平台 code(1淘宝/2抖音/3拼多多); 上游1688类任务不传, 归属留空")
    args = parser.parse_args()

    write_alert(args.key, args.msg, platform=args.platform, alert_type=args.type)
    return 0


if __name__ == "__main__":
    sys.exit(main())
