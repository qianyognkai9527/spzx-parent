#!/bin/bash
# db_daily.sh — 纯 DB 日常维护，一个入口（2026-10-19 合并，spec onsale-refactor 之后的整理）
# 原四个独立调度合一：04:10 db-backup(LaunchAgent) + 05:00 inventory_cron + 05:30 grade_quality
# 全程不碰 Chrome。顺序：备份 → 还原验证 → 告警检测 → 质量分级 → 磁盘卫生（每步独立留日志，一步失败不拦后步）
P=/Users/qyk9527/ideaProject/spzx-parent
LOG=/tmp/db_daily.log

echo "[$(date '+%F %T')] === db_daily 开始 ===" >> "$LOG"

# 1) 全量备份（42MB→gz 4MB，日留7天+周留8周）
bash "$P/scripts/backup-db.sh" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] backup rc=$?" >> "$LOG"

# 2) 还原进临时库验货（表数/锚点行/中文四判据）
bash "$P/scripts/verify-restore.sh" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] verify rc=$?" >> "$LOG"

# 3) 库存告警检测（detect_alerts：product_down/sku_down/price_change/source_dead → sync_alert）
"$P/automation/sourcing/inventory_cron.sh" pool >> /tmp/inventory_weekly.log 2>&1
echo "[$(date '+%F %T')] alerts rc=$?" >> "$LOG"

# 4) 质量分级（source_product 全量幂等重算）
cd "$P/automation/sourcing" && "$P/automation/venv/bin/python" grade_quality.py >> /tmp/cron_grades.log 2>&1
echo "[$(date '+%F %T')] grades rc=$?" >> "$LOG"

# 5) 磁盘卫生（日志裁剪+截图/探针清理, spec schedule-optimization §9; 纯文件操作不碰 Chrome）
bash "$P/scripts/cleanup_runtime.sh" >> "$LOG" 2>&1
echo "[$(date '+%F %T')] cleanup rc=$?" >> "$LOG"

echo "[$(date '+%F %T')] === db_daily 结束 ===" >> "$LOG"
