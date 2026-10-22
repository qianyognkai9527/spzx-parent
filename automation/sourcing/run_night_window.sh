#!/bin/bash
# 夜窗链（spec 2026-10-19-schedule-optimization §3）：03:00 LaunchAgent com.spzx.stock-refresh 触发。
# 夜巡(在售9页快照宇宙, 只读详情页) → ISV库存同步(唯一日常写) → 收9222。
# 串行而非三个定时器：夜巡最坏 2h（fetch 超时 65s×174 页），定时触发会撞死+被守卫跳过。
# 各段自带守卫/台账/告警；链只负责顺序与日志，任一段 rc!=0 不拦后段。
# DRY=1 时只打印计划不执行（链路验证用）。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
LOG=/tmp/night_window.log
if [ -n "${DRY:-}" ]; then
  echo "DRY: sleep $((RANDOM % 300)); run_stock_refresh.sh; run_stock_sync.sh; chrome_kill.sh"
  exit 0
fi
sleep $((RANDOM % 300))
echo "[$(date '+%F %T')] === 夜窗链 开始 ===" >> "$LOG"
bash "$DIR/run_stock_refresh.sh"
rc=$?
echo "[$(date '+%F %T')] 夜巡 rc=$rc" >> "$LOG"
bash "$DIR/run_stock_sync.sh"
rc=$?
echo "[$(date '+%F %T')] 同步 rc=$rc" >> "$LOG"
bash "$DIR/chrome_kill.sh"
echo "[$(date '+%F %T')] === 夜窗链 结束 ===" >> "$LOG"
