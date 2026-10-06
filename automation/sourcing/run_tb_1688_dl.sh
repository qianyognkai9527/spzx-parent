#!/bin/bash
# 1688 素材下载自愈循环: 撞风控(exit 42) → 阶梯冷却(10m→20m→1h 封顶) → 自动续跑。
# 每轮下载器自起全新 profile(详情页免登录), 绕开被 1688 打标的旧会话。
# 用法: ./run_tb_1688_dl.sh [--retry-failed] [--limit N] ...
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing || exit 1
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=${LOG:-/tmp/tb_1688_dl_wrap.log}
MAX_RETRY=${MAX_RETRY:-30}

LOCK=/tmp/tb_1688_dl.lock
if ! shlock -p $$ -f "$LOCK"; then
    echo "[$(date '+%m-%d %H:%M:%S')] 已有实例在运行(锁 $LOCK), 本次不启动" >> "$LOG"
    exit 1
fi

ATTEMPT=0
while [ $ATTEMPT -lt $MAX_RETRY ]; do
    ATTEMPT=$((ATTEMPT+1))
    echo "[$(date '+%m-%d %H:%M:%S')] === 第 $ATTEMPT/$MAX_RETRY 轮启动 ===" >> "$LOG"
    $PY download_1688_materials.py "$@" >> "$LOG" 2>&1
    CODE=$?
    echo "[$(date '+%m-%d %H:%M:%S')] 退出 code=$CODE" >> "$LOG"
    if [ $CODE -eq 42 ]; then
        case $ATTEMPT in
            1) CD=1200; CDM=20m ;;
            2) CD=2400; CDM=40m ;;
            *) CD=3600; CDM=1h ;;
        esac
        echo "[$(date '+%m-%d %H:%M:%S')] 1688风控, 冷却 ${CDM} 后自动续跑..." >> "$LOG"
        sleep $CD
    else
        echo "[$(date '+%m-%d %H:%M:%S')] 非风控退出(完成/异常), 循环结束" >> "$LOG"
        break
    fi
done
echo "[$(date '+%m-%d %H:%M:%S')] === 自愈循环结束 (共 $ATTEMPT 轮) ===" >> "$LOG"
