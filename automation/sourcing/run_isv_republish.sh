#!/bin/bash
# 美甲最小流程自愈 wrapper: 0=完成退出; 42=风控阶梯冷却(20m→40m→2h封顶); 其他=5m 重试
cd "$(dirname "$0")"
LOG=isv_republish_run.log
COOLDOWN=1200
while true; do
  /Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python assign_isv_republish.py >> "$LOG" 2>&1
  code=$?
  echo "[$(date '+%m-%d %H:%M:%S')] assign_nail_minimal 退出码=$code" >> "$LOG"
  if [ $code -eq 0 ]; then
    echo "[$(date '+%m-%d %H:%M:%S')] 全部处理完, wrapper 退出" >> "$LOG"
    break
  fi
  if [ $code -eq 42 ]; then
    echo "[$(date '+%m-%d %H:%M:%S')] 风控, 冷却 $((COOLDOWN/60))m 后自动续跑" >> "$LOG"
    sleep $COOLDOWN
    COOLDOWN=$(( COOLDOWN * 2 )); [ $COOLDOWN -gt 7200 ] && COOLDOWN=7200
  else
    echo "[$(date '+%m-%d %H:%M:%S')] 异常退出, 5m 后重试" >> "$LOG"
    sleep 300
  fi
done
