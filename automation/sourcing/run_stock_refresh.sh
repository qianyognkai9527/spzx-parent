#!/bin/bash
# 分级库存刷新（03:00，spec 2026-10-18 P2）。守卫同 inventory_cron。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/stock_refresh_cron.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=source_stock_change

skip() {
  local n
  n=$(bump_skip stock_refresh)
  echo "[$(date '+%m-%d %H:%M')] ($n) $1, 跳过本轮"
  $PY "$ALERT" --key stock_refresh --dataset "$DS" \
    --msg "$(skip_note stock_refresh)分级刷新未跑: $1" > /dev/null 2>&1
  local bid; bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
guard_task detect_stock_night 130 || skip "上一轮库存巡检未结束"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
pgrep -f backfill_offer_archive > /dev/null && skip "P1建档长跑占用同一 Chrome"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 分级刷新 开始 ===" >> $LOG
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
BID=$($PY "$BATCH" begin --dataset "$DS")
# [2026-10-19 M2] detect_stock_night：宇宙=在售快照(12:40 onsale_snapshot)，SKU 级详情页巡检只做
# 低库存(≤10)，快照已下架直接标死，另抽 10 个健康对照防控制台撒谎（spec onsale-refactor §3.3）
$PY detect_stock_night.py --low-threshold 10 --control 10 --delay 5 --stop-hour 5 >> $LOG 2>&1
rc=$?
SUMMARY=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" 2>/dev/null | grep '^SUMMARY ' | tail -1)
CHECKED=$(echo "$SUMMARY" | sed -n 's/.*checked=\([0-9]*\).*/\1/p')
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 分级刷新 结束 rc=$rc ===" >> $LOG
if [ "$rc" = "0" ]; then
  clear_skip stock_refresh
  $PY "$BATCH" end --id "$BID" --status success --rows-total "${CHECKED:-0}" --rows-ok "${CHECKED:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "detect_stock_night 异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key stock_refresh --dataset "$DS" --type cron_failed --msg "库存夜巡异常退出 rc=$rc" > /dev/null 2>&1
fi
