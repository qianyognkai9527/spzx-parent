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
  local n
  n=$(bump_skip sycm_snapshot)
  echo "[$(date '+%F %T')] ($n) $1, 跳过快照" >> "$LOG"
  $PY "$ALERT" --key sycm_snapshot --dataset "$DS" --platform 1 \
    --msg "$(skip_note sycm_snapshot)生意参谋每日快照未落库: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS" --platform 1)
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
guard_task sycm_item_snapshot 60 || skip "上一轮快照未结束"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"

cd "$DIR" || exit 0
sleep $((RANDOM % 180))
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
  clear_skip sycm_snapshot
  # rc=0 只说明脚本没报错，不说明采全了：翻页中途断掉时它照样正常退出并写 success。
  # 2026-10-02 实测 100 条 vs 平时 283 条仍记 success，靠行数才能判出来。
  V=$($PY "$BATCH" verdict --dataset "$DS" --rows "${ROWS:-0}" --exclude-id "$BID")
  if [ "$V" = "partial" ]; then
    $PY "$BATCH" end --id "$BID" --status partial --rows-total "${ROWS:-0}" --rows-ok "${ROWS:-0}" \
      --error "仅落库 ${ROWS:-0} 条，远低于近 5 轮中位数（多半只采到第一页或中途断）" > /dev/null 2>&1
    $PY "$ALERT" --key sycm_snapshot --dataset "$DS" --platform 1 --type cron_failed \
      --msg "生意参谋快照本轮只落了 ${ROWS:-0} 条（明显少于近期基线），商品效果/成交数据不完整，别拿去算利润" > /dev/null 2>&1
  else
    $PY "$BATCH" end --id "$BID" --status success --rows-total "${ROWS:-0}" --rows-ok "${ROWS:-0}" > /dev/null 2>&1
  fi
elif [ "$rc" = "42" ]; then
  $PY "$BATCH" end --id "$BID" --status failed --error "触发风控(rc=42), 已入库 ${ROWS:-0} 条" > /dev/null 2>&1
  $PY "$ALERT" --key sycm_snapshot --dataset "$DS" --platform 1 --type cron_failed --msg "生意参谋快照触发风控 rc=42（可能只落了部分页）" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "脚本异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key sycm_snapshot --dataset "$DS" --platform 1 --type cron_failed --msg "生意参谋快照脚本异常退出 rc=${rc}（1=报错）" > /dev/null 2>&1
fi
exit $rc
