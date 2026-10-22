#!/bin/bash
# 19:30 事件驱动补偿（spec 2026-10-19-schedule-optimization §5）。
# 无事件: 一行日志退出, 不拉 Chrome, 不写台账（新鲜度面板无批次属预期, 口径见注册表 remark）。
# 有事件: ensure_chrome+ensure_login → 复用 run_stock_sync.sh（9 页在售口径）。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/stock_event_sync.log
echo "[$(date '+%F %T')] === 事件检查 开始 ===" >> "$LOG"
if [ "${1:-}" = "--check" ]; then
  "$PY" "$DIR/stock_event_check.py"; echo "exit=$?"; exit 0
fi
EV=$("$PY" "$DIR/stock_event_check.py" 2>>"$LOG") || { echo "[$(date '+%F %T')] 判定异常" >> "$LOG"; exit 1; }
if ! echo "$EV" | grep -q "^EVENT$"; then
  echo "[$(date '+%F %T')] $(echo "$EV" | tail -1) → 无库存事件, 不拉 Chrome" >> "$LOG"
  exit 0
fi
echo "[$(date '+%F %T')] $(echo "$EV" | tail -1) → 补跑同步" >> "$LOG"
bash "$DIR/run_stock_sync.sh"
bash "$DIR/chrome_kill.sh"
echo "[$(date '+%F %T')] === 事件检查 结束 ===" >> "$LOG"
