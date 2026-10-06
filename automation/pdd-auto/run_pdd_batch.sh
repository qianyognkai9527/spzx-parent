#!/usr/bin/env bash
# PDD 批量铺货管线: 采集(千牛) -> 构建worklist(下载图×1.3) -> 发布(PDD, 冷却循环)
# 可断点续跑: 三阶段各自跳过已完成的. 日志 batch_pipeline.log
cd "$(dirname "$0")"
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
LOG=batch_pipeline.log
{
  echo "===== [$(date '+%F %T')] 阶段1 采集(千牛) ====="
  $PY collect_qianniu.py --from-isv
  echo "===== [$(date '+%F %T')] 阶段2 构建 worklist(下载图/缩1080/×1.3) ====="
  $PY build_pdd_worklist.py
  echo "===== [$(date '+%F %T')] 阶段3 发布(PDD) ====="
  bash run_pdd_all.sh
  echo "===== [$(date '+%F %T')] 管线结束 ====="
} >> "$LOG" 2>&1
