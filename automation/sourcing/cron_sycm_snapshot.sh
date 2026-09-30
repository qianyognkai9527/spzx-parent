#!/usr/bin/env bash
# 每日 生意参谋 商品效果快照 (2026-09-08)
# 9222 窗口模式 Chrome 必需(headless 会被 RGV587 拦)。9222 不在线则跳过。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/sycm_daily_cron.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=item_daily_sycm

# 跳过也留一行批次台账：跑批历史必须完整，否则"没跑"和"跑了没记录"分不开
skip() {
  echo "[$(date '+%F %T')] $1, 跳过快照" >> "$LOG"
  $PY "$ALERT" --key sycm_snapshot --platform 1 --msg "生意参谋每日快照未落库: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

# 守卫: 9222 在线检查
curl -s --max-time 3 http://127.0.0.1:9222/json/version > /dev/null 2>&1 || skip "Chrome 9222 不在线"
curl -s --max-time 3 http://127.0.0.1:9222/json/list 2>/dev/null | grep -q '"type": "page"' || skip "Chrome 9222 无可用标签页"

cd "$DIR" || exit 0
BIZ_TO=$(date -v-1d +%F)
BIZ_FROM=$(date -v-7d +%F)
BID=$($PY "$BATCH" begin --dataset "$DS" --platform 1 --biz-from "$BIZ_FROM" --biz-to "$BIZ_TO")

echo "[$(date '+%F %T')] 开始快照" >> "$LOG"
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
$PY sycm_item_snapshot.py --date-type recent7 >> "$LOG" 2>&1
rc=$?
echo "[$(date '+%F %T')] 退出码 $rc" >> "$LOG"

# 脚本自己会打「入库 N 条」；只在本轮新增的日志片段里取，否则会读到上一轮的数字。取不到留 0（未上报）
ROWS=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" | sed -n "s/.*入库 \\([0-9]*\\) 条.*/\\1/p" | tail -1)
if [ "$rc" = "0" ]; then
  $PY "$BATCH" end --id "$BID" --status success --rows-total "${ROWS:-0}" --rows-ok "${ROWS:-0}" > /dev/null 2>&1
elif [ "$rc" = "42" ]; then
  $PY "$BATCH" end --id "$BID" --status failed --error "触发风控(rc=42), 已入库 ${ROWS:-0} 条" > /dev/null 2>&1
  $PY "$ALERT" --key sycm_snapshot --platform 1 --type cron_failed --msg "生意参谋快照触发风控 rc=42（可能只落了部分页）" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "脚本异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key sycm_snapshot --platform 1 --type cron_failed --msg "生意参谋快照脚本异常退出 rc=${rc}（1=报错）" > /dev/null 2>&1
fi
exit $rc
