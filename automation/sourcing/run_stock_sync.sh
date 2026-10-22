#!/bin/bash
# ISV 全量库存同步定时调度（1688 货源库存 → 淘宝 SKU）
# 流程 = 控制台「已关联货源」逐页 100条/页 全选 →「批量同步库存」→ 确定（isv_stock_sync.py）
# 用法: run_stock_sync.sh   （03:00 夜窗链内 + 19:30 事件补偿（run_stock_event_sync.sh）调用）
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
cd "$DIR" || exit 0
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/stock_sync_cron.log
ALERT=$DIR/cron_alert.py
BATCH=$DIR/cron_batch.py
DS=isv_stock_sync

skip() {
  local n
  n=$(bump_skip stock_sync)
  echo "[$(date '+%m-%d %H:%M')] ($n) $1, 跳过本轮"
  $PY "$ALERT" --key stock_sync --dataset "$DS" \
    --msg "$(skip_note stock_sync)库存同步未跑: $1" > /dev/null 2>&1
  local bid
  bid=$($PY "$BATCH" begin --dataset "$DS")
  $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  exit 0
}

# 守卫: Chrome 9222 不在线 → 静默拉起；再验登录态（掉了=显式告警+skip, 不自动重登）
source "$DIR/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
# 守卫: 自互斥+防僵死（上一轮 >60min 判 hung 终止后放行）
guard_task isv_stock_sync 60 || skip "上一轮库存同步未结束"
# 守卫: 定时任务互避（超龄自动终止；此处 max 均为各任务正常耗时的 2 倍以上）
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
guard_task collect_alimama_promo 120 || skip "推广日报采集占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
# 守卫: 用户长任务（合法小时级长跑, 永不自动杀）→ 纯避让
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"
pgrep -f backfill_offer_archive > /dev/null && skip "P1建档长跑占用同一 Chrome"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === ISV库存同步 开始 ===" >> $LOG
BID=$($PY "$BATCH" begin --dataset "$DS")
$PY isv_stock_sync.py >> $LOG 2>&1
rc=$?
# 产物: stock_sync_report.json 的 pages 合计行数
ROWS=$($PY -c "import json;d=json.load(open('$DIR/stock_sync_report.json'));print(sum(v['rows'] for v in d['pages'].values()))" 2>/dev/null || echo 0)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] === ISV库存同步 结束 rc=$rc rows=$ROWS ===" >> $LOG
if [ "$rc" = "0" ]; then
  # 行级核验（spec P4）：0库存商品的同步记录抽查，写 stock_sync_check，异常写告警
  $PY isv_sync_verify.py --cap 50 >> $LOG 2>&1 || true
  clear_skip stock_sync
  $PY "$BATCH" end --id "$BID" --status success --rows-total "${ROWS:-0}" --rows-ok "${ROWS:-0}" > /dev/null 2>&1
else
  $PY "$BATCH" end --id "$BID" --status failed --error "isv_stock_sync 异常退出 rc=$rc" > /dev/null 2>&1
  $PY "$ALERT" --key stock_sync --dataset "$DS" --type cron_failed --msg "ISV库存同步异常退出 rc=$rc" > /dev/null 2>&1
fi
