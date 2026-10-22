#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock_event_check.py — 19:30 事件驱动补偿判定（spec 2026-10-19-schedule-optimization §5）

触发 = 当天新写且未读的库存类 sync_alert（白名单 4 类: isv_sync_fail/source_dead/
onsale_binding_change/onsale_mismatch）∪ 今天无 isv_stock_sync success 批次。
low_stock/oversell_risk 属中午扫描每天重算的常规状态, 2026-10-19 owner 决定移出事件集。
限定「当天新写」：陈年未读不触发（否则事件驱动失效）。纯 DB, 不碰 Chrome。
打印 EVENT / NO_EVENT；exit 0=判定完成, 1=判定异常。
"""
import sys
import time

sys.path.insert(0, '/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing')
from dbconf import DB_CONFIG

WHITELIST = {"isv_sync_fail", "source_dead", "onsale_binding_change", "onsale_mismatch"}


def decide(alert_rows, has_success_batch):
    """纯函数。alert_rows: [{alert_type,status,create_time}]（create_time 'YYYY-MM-DD HH:MM:SS'）。"""
    today = time.strftime('%Y-%m-%d')
    hits = [r for r in alert_rows
            if r.get("alert_type") in WHITELIST
            and r.get("status") == 0
            and str(r.get("create_time") or "")[:10] == today]
    if hits:
        types = sorted({r["alert_type"] for r in hits})
        return True, f"当天新写库存告警 {len(hits)} 条: {','.join(types)}"
    if not has_success_batch:
        return True, "今日无 isv_stock_sync success 批次（夜窗未跑成）"
    return False, "无库存事件"


def main():
    import pymysql
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        today = time.strftime('%Y-%m-%d')
        cur.execute(
            "SELECT alert_type, status, create_time FROM sync_alert "
            "WHERE DATE(create_time)=%s", (today,))
        rows = [{"alert_type": a, "status": s, "create_time": t} for a, s, t in cur.fetchall()]
        cur.execute(
            "SELECT COUNT(*) FROM ingest_batch "
            "WHERE dataset='isv_stock_sync' AND status='success' AND DATE(create_time)=%s",
            (today,))
        has_ok = cur.fetchone()[0] > 0
        cur.close()
    finally:
        conn.close()
    ok, why = decide(rows, has_ok)
    print("EVENT" if ok else "NO_EVENT")
    print(why)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"CHECK_ERROR {e!r}", file=sys.stderr)
        sys.exit(1)
