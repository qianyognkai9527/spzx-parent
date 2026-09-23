#!/bin/bash
# 每周六 03:30: 运费补抓 (9223)
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=/tmp/cron_freight.log

curl -s --max-time 5 http://127.0.0.1:9223/json/version > /dev/null || { echo "[$(date '+%m-%d %H:%M')] Chrome 9223 不在线, 跳过"; exit 0; }
pgrep -f "fix_scrape_images|create_douyin_product|fix_douyin_images" > /dev/null && { echo "[$(date '+%m-%d %H:%M')] 抖音链运行中, 跳过"; exit 0; }

echo "[$(date '+%m-%d %H:%M')] === fetch_freight 开始 ===" >> $LOG
$PY fetch_freight.py >> $LOG 2>&1
echo "[$(date '+%m-%d %H:%M')] === fetch_freight 结束 ===" >> $LOG
