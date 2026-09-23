#!/usr/bin/env bash
# 每日 生意参谋 商品效果快照 (2026-09-08)
# 9222 窗口模式 Chrome 必需(headless 会被 RGV587 拦)。9222 不在线则跳过。
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/sycm_daily_cron.log

# 守卫: 9222 在线检查
if ! curl -s --max-time 3 http://127.0.0.1:9222/json/version > /dev/null 2>&1; then
  echo "[$(date '+%F %T')] 9222 Chrome 不在线, 跳过快照" >> "$LOG"
  exit 0
fi
if curl -s --max-time 3 http://127.0.0.1:9222/json/list 2>/dev/null | grep -q '"type": "page"'; then
  :
else
  echo "[$(date '+%F %T')] 9222 target 为空, 跳过快照" >> "$LOG"
  exit 0
fi

cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
echo "[$(date '+%F %T')] 开始快照" >> "$LOG"
$PY sycm_item_snapshot.py --date-type recent7 >> "$LOG" 2>&1
rc=$?
echo "[$(date '+%F %T')] 退出码 $rc" >> "$LOG"
exit $rc
