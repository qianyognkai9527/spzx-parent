#!/bin/bash
# 窗口外收 9222 (13:10（中午窗口尾）；夜间由夜窗链尾自收（run_night_window，勿写 .sh 后缀：
# check-consistency 的 cron_targets 会扫脚本正文里的 *.sh 当链式目标，写了就误把夜窗全链挂到本作业）。
# 有任务在跑 → 放过并留日志。
LOG=/tmp/chrome_kill.log
BUSY="isv_stock_sync|detect_stock_|collect_alimama|sycm_item_snapshot|sync_onsale|isv_sku_match|assign_shop_category_v2|edit_brand_title_batch|backfill_offer_archive|probe_"
if pgrep -f "$BUSY" >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] 任务在跑, 保留 Chrome" >> "$LOG"
  exit 0
fi
if pkill -f "remote-debugging-port=9222"; then
  echo "[$(date '+%F %T')] 已收 9222" >> "$LOG"
else
  echo "[$(date '+%F %T')] 本来就不在线" >> "$LOG"
fi
