#!/usr/bin/env bash
# 每日 阿里妈妈(万相台无界版)推广日报采集：计划粒度 + 宝贝粒度 (2026-10-03)
#
# 数据落在 promo_cost_daily / promo_cost_item_daily，采集脚本自己写 ingest_batch 台账
# （与 sycm 那条链不同 —— 那边台账在包装脚本里，这里已经内聚到 python 侧）。
# 所以本脚本只负责三件事：守卫、跳过留痕、退出码告警。
#
# 依赖 9222（tb-auto Chrome，带淘宝/阿里妈妈登录态）。窗口模式必需，headless 易被 RGV587 拦。
# 成交类指标有归因回补，所以每天滚动重拉 15 天，靠唯一键 upsert 覆盖旧值 —— 不是只采昨天。
DIR=/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
SRC=/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/alimama_promo_cron.log
ALERT=$SRC/cron_alert.py
BATCH=$SRC/cron_batch.py
DATASETS="promo_cost promo_cost_detail"
KEY=alimama_promo
DS=promo_cost   # 提醒销案认这个数据集code（该作业还会写 promo_cost_detail，取主口径那个）
DAYS=15

# 跳过也要留一行批次台账 + 一条提醒：跑批历史必须完整，否则"没跑"和"跑了没记录"分不开；
# 而台账记 failed 不会把新鲜度顶成"刚采过"（lastBatchAt 只认 success/partial）。
skip() {
  local n
  n=$(bump_skip alimama_promo)
  echo "[$(date '+%F %T')] ($n) $1, 跳过采集" >> "$LOG"
  $PY "$ALERT" --key "$KEY" --dataset "$DS" --platform 1 \
    --msg "$(skip_note alimama_promo)推广日报采集未落库: $1" > /dev/null 2>&1
  for ds in $DATASETS; do
    local bid
    bid=$($PY "$BATCH" begin --dataset "$ds" --platform 1)
    $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  done
  exit 0
}

# 守卫 1: MySQL 不在线就不必再往下走
nc -z 127.0.0.1 3306 || skip "MySQL 3306 未监听"
# 守卫 2: Chrome 9222 静默拉起 + 登录态预检
source "$SRC/chrome_guard.sh"
ensure_chrome || skip "Chrome 9222 静默拉起失败"
ensure_login || skip "9222 登录态失效（需人工扫码）"
# 守卫 3: 定时任务互避（超龄自动终止）+ 用户长任务纯避让
guard_task collect_alimama_promo 120 || skip "上一轮采集未结束"
guard_task sycm_item_snapshot 60 || skip "生意参谋快照占用同一 Chrome"
guard_task isv_stock_sync 60 || skip "库存同步占用同一 Chrome"
guard_task sync_onsale 30 || skip "在售扫描占用同一 Chrome"
guard_task detect_stock_night 130 || skip "库存夜巡占用同一 Chrome"
pgrep -f assign_shop_category_v2 > /dev/null && skip "归类v2占用同一 Chrome"
pgrep -f edit_brand_title_batch > /dev/null && skip "品牌批处理占用同一 Chrome"
pgrep -f isv_sku_match > /dev/null && skip "ISV规格匹配占用同一 Chrome"

cd "$DIR" || exit 0
sleep $((RANDOM % 300))
echo "[$(date '+%F %T')] 开始采集（滚动 ${DAYS} 天，计划+宝贝+人群+词四层）" >> "$LOG"
$PY collect_alimama_promo.py --level all --days "$DAYS" --gap 4 \
  --crowd-campaign-ids 83392643008,84290744044 \
  --word-campaign-ids 84290744044 \
  --include-campaign-ids 83949710619,83340870410 >> "$LOG" 2>&1
rc=$?
echo "[$(date '+%F %T')] 退出码 $rc" >> "$LOG"
if [ "$rc" = "0" ]; then clear_skip alimama_promo; fi

# 台账由 python 自己收尾，这里只补运维提醒：新鲜度巡检最快一小时后才从库里判出来，
# 这段静默窗口要靠告警补齐。
if [ "$rc" = "42" ]; then
  $PY "$ALERT" --key "$KEY" --dataset "$DS" --platform 1 --type cron_failed --msg "推广日报采集触发风控 rc=42（可能只采到部分天，已自动冷却等待下轮）" > /dev/null 2>&1
elif [ "$rc" != "0" ]; then
  $PY "$ALERT" --key "$KEY" --dataset "$DS" --platform 1 --type cron_failed --msg "推广日报采集异常退出 rc=${rc}（1=有错误或未采全）" > /dev/null 2>&1
fi
exit $rc
