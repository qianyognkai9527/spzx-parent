#!/bin/bash
# cleanup_runtime.sh — 磁盘卫生（spec 2026-10-19-schedule-optimization §9），db_daily 第 5 步。
# 1) /tmp spzx 系日志 >2MB 裁尾 2000 行（台账真源在 ingest_batch, 日志中段历史可丢）
# 2) 截图清理：模式白名单 + mtime>7 天（禁止按扩展名全域扫删——pdd_images 输入素材混在图片里）
# 3) /tmp spzx 探针残留 mtime>14 天
# 绝不触碰：chrome-profile*（登录态）/ pdd_images* / novel_batches / douyin_reports / ~/Backups/spzx-db/
# 用法: cleanup_runtime.sh [--dry-run]
P=/Users/qyk9527/ideaProject/spzx-parent
LOG=/tmp/cleanup_runtime.log
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
DEL=0; FREE=0
say() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

rm_one() {
  local f="$1" s
  s=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if [ "$DRY" = "1" ]; then echo "DRY_DEL $f ($((s / 1024))KB)"; else rm -f "$f"; fi
  DEL=$((DEL + 1)); FREE=$((FREE + s))
}

# 1) 日志裁剪
for f in /tmp/cron_stats.log /tmp/sycm_daily_cron.log /tmp/alimama_promo_cron.log \
         /tmp/stock_sync_cron.log /tmp/stock_refresh_cron.log /tmp/onsale_scan.log \
         /tmp/inventory_cron.log /tmp/inventory_weekly.log /tmp/chrome_kill.log \
         /tmp/backfill_night_run.log /tmp/db_daily.log /tmp/night_window.log \
         /tmp/stock_event_sync.log /tmp/cleanup_runtime.log /tmp/cron_collect_full.log \
         /tmp/sku_match_run.log /tmp/cat_v2_wrap.log /tmp/brand_run.log; do
  [ -f "$f" ] || continue
  sz=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if [ "$sz" -gt 2097152 ]; then
    say "裁剪 $f ($((sz / 1024))KB → 末尾2000行)"
    [ "$DRY" = "0" ] && { tail -n 2000 "$f" > "$f.tmp" && mv "$f.tmp" "$f"; }
  fi
done

# 2) 截图（模式白名单 + 7 天）
for f in "$P"/automation/tb-auto/test_screenshot_*.png \
         "$P"/automation/tb-auto/submit_unknown_*.png \
         /tmp/sycm_noapi.png; do
  [ -e "$f" ] || continue
  [ -n "$(find "$f" -mtime +7 2>/dev/null)" ] && rm_one "$f"
done

# 3) /tmp spzx 探针残留（14 天）
for f in /tmp/spzx_* /tmp/noon_* /tmp/sku_direct_probe*; do
  [ "$f" = "/tmp/spzx_my.cnf" ] && continue   # DB 临时凭据，14 天规则不适用（可由 mysql-cnf.py 重建）
  [ -e "$f" ] || continue
  [ -n "$(find "$f" -mtime +14 2>/dev/null)" ] && rm_one "$f"
done

say "=== 清理完成 del=$DEL free=$((FREE / 1024))KB dry=$DRY ==="
echo "cleanup: del=$DEL free=$((FREE / 1024))KB dry=$DRY"
