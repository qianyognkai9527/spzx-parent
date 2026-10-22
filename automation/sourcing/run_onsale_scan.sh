#!/bin/bash
# 每日 12:50 铺货平台在售扫描 (LaunchAgent com.spzx.onsale-scan, spec onsale-refactor §3.1)
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/onsale_scan.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=onsale_scan

skip() {
  local n
  n=$(bump_skip onsale_scan)
  echo "[$(date '+%m-%d %H:%M')] ($n) $1, 跳过" >> "$LOG"
  $PY "$ALERT" --key onsale_scan --dataset "$DS" --platform 1 \
    --msg "$(skip_note onsale_scan)在售扫描未跑: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

sleep $((RANDOM % 180))
source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
guard_task sync_onsale 30 || skip "上一轮未结束"
guard_task sycm_item_snapshot 60 || skip "生意参谋快照占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
pgrep -f assign_shop_category_v2 >/dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch >/dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match >/dev/null && skip "ISV规格匹配占用同一 Chrome"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 在售扫描 开始 ===" >> "$LOG"
LINES_BEFORE=$(wc -l < "$LOG" 2>/dev/null || echo 0)
BID=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
$PY sync_onsale.py "$@" >> "$LOG" 2>&1
rc=$?
ROWS=$(tail -n +$((LINES_BEFORE + 1)) "$LOG" 2>/dev/null | sed -n "s/.*入库 \([0-9]*\) 条.*/\1/p" | tail -1)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 在售扫描 结束 rc=$rc rows=${ROWS:-0} ===" >> "$LOG"
if [ "$rc" = "0" ]; then
  clear_skip onsale_scan
  $PY "$BATCH" end --id "$BID" --status success --rows-total "${ROWS:-0}" --rows-ok "${ROWS:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "sync_onsale 异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key onsale_scan --dataset "$DS" --platform 1 --type cron_failed --msg "在售扫描异常退出 rc=$rc" > /dev/null 2>&1
fi
ensure_chrome   # 退出兜底: 防 0 标签病态
exit $rc
