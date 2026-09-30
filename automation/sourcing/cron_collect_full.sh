#!/bin/bash
# 每周六 03:00: 1688详情采集合并(SKU/库存/运费/销量补全, 为尺码同步攒数据)
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/cron_collect_full.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
# 1688 货源侧上游，跨平台复用 → 批次不带 platform
DS=source_sku

skip() {
  echo "[$(date '+%m-%d %H:%M')] $1, 跳过"
  $PY "$ALERT" --key collect_1688_full --msg "1688详情周采集未落库: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

curl -s --max-time 5 http://127.0.0.1:9222/json/version > /dev/null || skip "Chrome 9222 不在线"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome, 本周让路"

echo "[$(date '+%m-%d %H:%M')] === collect_1688_full 开始 ===" >> $LOG
BID=$($PY "$BATCH" begin --dataset "$DS")
$PY collect_1688_full.py >> $LOG 2>&1
rc=$?
echo "[$(date '+%m-%d %H:%M')] === collect_1688_full 结束 rc=$rc ===" >> $LOG
if [ "$rc" = "0" ]; then
  $PY "$BATCH" end --id "$BID" --status success > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "脚本异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key collect_1688_full --type cron_failed --msg "1688详情周采集脚本异常退出 rc=$rc" > /dev/null 2>&1
fi
