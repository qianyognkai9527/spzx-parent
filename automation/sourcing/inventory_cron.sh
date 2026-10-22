#!/bin/bash
# 库存同步定时调度
# 用法: inventory_cron.sh [pool|full]  (默认 pool=优质池, full=全部商品)
# [2026-10-18] 采集已迁 03:00 LaunchAgent com.spzx.stock-refresh（detect_stock_change --tiered）。
# 本脚本(crontab 05:00)只保留 detect_alerts 提醒检测。crontab 行不可程序化删除，物理保留。
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
  $PY "$ALERT" --key inventory_sync --dataset "$DS" --msg "库存日同步未跑: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

# [2026-10-19] 采集已迁 03:00, 本脚本只剩纯 DB 的 detect_alerts —— Chrome/pgrep 守卫全部移除
# （原「Chrome 不在线→跳过」会让纯 DB 的提醒检测陪葬, 还误报库存同步未跑）

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 库存提醒检测 $MODE 开始 ===" >> $LOG
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)

# 检测提醒（独立台账；采集迁走后它是本脚本唯一的活）
ARB=$($PY "$BATCH" begin --dataset "$DS_ALERT")
$PY detect_alerts.py --type all >> $LOG 2>&1
arc=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 库存提醒检测 $MODE 结束 提醒检测 rc=$arc ===" >> $LOG
# detect_alerts 每种检测各打一行「新增 N 条」，求和=本轮新写提醒数；取本轮新增片段避免继承上轮
ALERT_LINES=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" 2>/dev/null | sed -n "s/.*新增 \([0-9]*\) 条.*/\\1/p")
ALERT_ROWS=$(echo "${ALERT_LINES:-0}" | paste -sd+ - | bc 2>/dev/null || echo 0)
if [ "$arc" = "0" ]; then
  $PY "$BATCH" end --id "$ARB" --status success --rows-total "${ALERT_ROWS:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$ARB" --status failed --error "detect_alerts 异常退出 rc=$arc" > /dev/null 2>&1
  $PY "$ALERT" --key alert_detect --dataset "$DS_ALERT" --type cron_failed --msg "货源下架/变价提醒检测异常退出 rc=${arc}（product_down/sku_down/price_change 三类提醒停摆）" > /dev/null 2>&1
fi
