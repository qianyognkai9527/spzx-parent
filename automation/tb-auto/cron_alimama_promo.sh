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
DAYS=15

# 跳过也要留一行批次台账 + 一条提醒：跑批历史必须完整，否则"没跑"和"跑了没记录"分不开；
# 而台账记 failed 不会把新鲜度顶成"刚采过"（lastBatchAt 只认 success/partial）。
skip() {
  echo "[$(date '+%F %T')] $1, 跳过采集" >> "$LOG"
  $PY "$ALERT" --key "$KEY" --platform 1 --msg "推广日报采集未落库: $1" > /dev/null 2>&1
  for ds in $DATASETS; do
    local bid
    bid=$($PY "$BATCH" begin --dataset "$ds" --platform 1)
    $PY "$BATCH" end --id "$bid" --status failed --error "$1" > /dev/null 2>&1
  done
  exit 0
}

# 守卫 1: MySQL 不在线就不必再往下走（本机 MySQL 是原生常驻，重启后不自启）
nc -z 127.0.0.1 3306 || skip "MySQL 3306 未监听"
# 守卫 2: 9222 在线 + 有可用标签页（0 标签时 connect_over_cdp 会报错）
curl -s --max-time 5 http://127.0.0.1:9222/json/version > /dev/null || skip "Chrome 9222 不在线"
curl -s --max-time 5 http://127.0.0.1:9222/json/list 2>/dev/null | grep -q '"type": "page"' || skip "Chrome 9222 无可用标签页"
# 守卫 3: 同一个 Chrome 上别的采集任务在跑就避让（账号级风控，跨实例也会互触）
pgrep -f "sycm_item_snapshot|assign_shop_category|collect_1688_full|collect_in_stock_current|detect_stock|auto_list|edit_isv_drafts|cron_collect_full" > /dev/null \
  && skip "9222 上有其他采集任务在跑"

cd "$DIR" || exit 0
echo "[$(date '+%F %T')] 开始采集（滚动 ${DAYS} 天，计划+宝贝两层）" >> "$LOG"
$PY collect_alimama_promo.py --level both --days "$DAYS" --gap 4 >> "$LOG" 2>&1
rc=$?
echo "[$(date '+%F %T')] 退出码 $rc" >> "$LOG"

# 台账由 python 自己收尾，这里只补运维提醒：新鲜度巡检最快一小时后才从库里判出来，
# 这段静默窗口要靠告警补齐。
if [ "$rc" = "42" ]; then
  $PY "$ALERT" --key "$KEY" --platform 1 --type cron_failed --msg "推广日报采集触发风控 rc=42（可能只采到部分天，已自动冷却等待下轮）" > /dev/null 2>&1
elif [ "$rc" != "0" ]; then
  $PY "$ALERT" --key "$KEY" --platform 1 --type cron_failed --msg "推广日报采集异常退出 rc=${rc}（1=有错误或未采全）" > /dev/null 2>&1
fi
exit $rc
