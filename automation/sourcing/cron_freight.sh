#!/bin/bash
# 每周六 03:30: 运费补抓 (9223)
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/cron_freight.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=source_freight

skip() {
  echo "[$(date '+%m-%d %H:%M')] $1, 跳过"
  $PY "$ALERT" --key fetch_freight --msg "运费周补抓未落库: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

curl -s --max-time 5 http://127.0.0.1:9223/json/version > /dev/null || skip "Chrome 9223 不在线"
pgrep -f "fix_scrape_images|create_douyin_product|fix_douyin_images" > /dev/null && skip "9223 被抖店链路占用, 本周让路"

echo "[$(date '+%m-%d %H:%M')] === fetch_freight 开始 ===" >> $LOG
BID=$($PY "$BATCH" begin --dataset "$DS")
$PY fetch_freight.py >> $LOG 2>&1
rc=$?
echo "[$(date '+%m-%d %H:%M')] === fetch_freight 结束 rc=$rc ===" >> $LOG
if [ "$rc" = "0" ]; then
  $PY "$BATCH" end --id "$BID" --status success > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "脚本异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key fetch_freight --type cron_failed --msg "运费周补抓脚本异常退出 rc=$rc" > /dev/null 2>&1
fi
