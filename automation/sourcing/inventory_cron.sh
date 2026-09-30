#!/bin/bash
# 库存同步定时调度
# 用法: inventory_cron.sh [pool|full]  (默认 pool=优质池, full=全部商品)
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/inventory_cron.log
MODE=${1:-pool}
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=source_stock_change
DS_ALERT=source_alert_detect

skip() {
  echo "[$(date '+%m-%d %H:%M')] $1, 跳过本轮"
  $PY "$ALERT" --key inventory_sync --msg "库存日同步未跑: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

# 守卫: Chrome 9222 不在线 → 跳过
curl -s --max-time 5 http://127.0.0.1:9222/json/version > /dev/null || skip "Chrome 9222 不在线"
# 守卫: 归类v2运行中(同Chrome勿并行1688任务) → 跳过
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 库存同步 $MODE 开始 ===" >> $LOG
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
BID=$($PY "$BATCH" begin --dataset "$DS")

# 1. 采集1688 SKU + 检测变化 (默认只扫优质池, full扫全部)
if [ "$MODE" = "full" ]; then
    $PY detect_stock_change.py >> $LOG 2>&1
else
    $PY detect_stock_change.py --pool >> $LOG 2>&1
fi
rc=$?

# 2. 检测提醒（独立台账：它跑挂不能借第 1 步的 rc 蒙混过关）
ARB=$($PY "$BATCH" begin --dataset "$DS_ALERT")
$PY detect_alerts.py --type all >> $LOG 2>&1
arc=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 库存同步 $MODE 结束 rc=$rc 提醒检测 rc=$arc ===" >> $LOG
# detect_alerts 每种检测各打一行「新增 N 条」，求和=本轮新写提醒数；取本轮新增片段避免继承上轮
ALERT_LINES=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" 2>/dev/null | sed -n "s/.*新增 \([0-9]*\) 条.*/\\1/p")
ALERT_ROWS=$(echo "${ALERT_LINES:-0}" | paste -sd+ - | bc 2>/dev/null || echo 0)
if [ "$rc" = "0" ]; then
  $PY "$BATCH" end --id "$BID" --status success > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "detect_stock_change 异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key inventory_sync --type cron_failed --msg "库存日同步脚本异常退出 rc=$rc" > /dev/null 2>&1
fi
if [ "$arc" = "0" ]; then
  $PY "$BATCH" end --id "$ARB" --status success --rows-total "${ALERT_ROWS:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$ARB" --status failed --error "detect_alerts 异常退出 rc=$arc" > /dev/null 2>&1
  $PY "$ALERT" --key alert_detect --type cron_failed --msg "货源下架/变价提醒检测异常退出 rc=${arc}（product_down/sku_down/price_change 三类提醒停摆）" > /dev/null 2>&1
fi
