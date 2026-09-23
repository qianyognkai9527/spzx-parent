#!/bin/bash
# run_douyin_all.sh — 瑰若抖店直建流水线编排 (工作清单→抓详情→建商品), 各阶段可断点续跑
cd /Users/qyk9527/ideaProject/spzx-parent/automation/sourcing
PY=/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python
export LANG=en_US.UTF-8

log() { echo "[$(date '+%H:%M:%S')] $1"; }

# ---- Stage 1: 工作清单 (直到一轮无新增才停, 最多30轮应对限流) ----
log "=== Stage 1: build_douyin_worklist ==="
for i in $(seq 1 30); do
  before=$(wc -l < douyin_worklist.jsonl 2>/dev/null || echo 0)
  $PY build_douyin_worklist.py >> build_worklist_all.log 2>&1
  after=$(wc -l < douyin_worklist.jsonl 2>/dev/null || echo 0)
  log "  工作清单轮$i: $before -> $after"
  if [ "$after" -le "$before" ]; then
    log "  工作清单无新增, 进入 Stage 2"
    break
  fi
  sleep 20
done

# ---- Stage 2: 抓详情 (直到一轮无新增才停) ----
log "=== Stage 2: scrape_1688_for_douyin ==="
for i in $(seq 1 60); do
  before=$(wc -l < douyin_product_data.jsonl 2>/dev/null || echo 0)
  $PY scrape_1688_for_douyin.py >> scrape_all.log 2>&1
  after=$(wc -l < douyin_product_data.jsonl 2>/dev/null || echo 0)
  log "  抓详情轮$i: $before -> $after"
  if [ "$after" -le "$before" ]; then
    log "  抓详情无新增, 进入 Stage 3"
    break
  fi
  sleep 15
done

# ---- Stage 3: 建商品 (每次一个大批次, 跑完自动停) ----
log "=== Stage 3: create_douyin_product ==="
for i in $(seq 1 200); do
  $PY create_douyin_product.py --batch 99999 >> create_all.log 2>&1
  if grep -q "没有待处理商品" create_all.log; then
    log "  建商品全部完成"
    break
  fi
  log "  建商品轮$i 完成(还有剩余, 续跑)"
  sleep 10
done

log "=== 流水线结束 ==="
