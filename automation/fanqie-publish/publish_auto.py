#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《万域邪主》自动发布循环: 处理番茄每日字数上限 + 每日限额分批发布.

策略:
  - 每天 12:00 开始发布, 每次最多发 DAILY_LIMIT 章 (规避番茄每日字数上限)
  - 若遇「提交字数超出每日上限」返回码 3, 等下一自然日再试
  - 若当日限额发完或全部发完(返回码 0), 检查是否还有待发章节:
      有 -> 等下一自然日继续; 无 -> 退出
  - 其他失败(返回码 2) -> 暂停等人工
"""
import datetime
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "publish_fanqie.py")
STATE = os.path.join(HERE, "fanqie_publish_state.json")
PROG = os.path.join(HERE, "publish_progress.json")
LOG = os.path.join(HERE, "publish_auto.log")
PY = "/Users/qyk9527/ideaProject/spzx-parent/automation/venv/bin/python"

DAILY_LIMIT = 8                # 每天最多发布的章节数(每日约1.8万字, 番茄日上限实测~4.9万, 安全)
START_HOUR, START_MIN = 12, 0  # 每天开始发布时刻 (字数上限非0点刷新, 实测中午刷新, 改12点发布)
STATE_READ_FAIL_MAX = 6        # 待发状态连续读取失败上限(每10分钟重查一次, 1小时后退出等人工)


def log(msg):
    line = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def wait_until_next_day():
    """等待到下一个自然日 START_HOUR:START_MIN."""
    now = datetime.datetime.now()
    tomorrow = now + datetime.timedelta(days=1)
    target = tomorrow.replace(hour=START_HOUR, minute=START_MIN, second=0, microsecond=0)
    delta = (target - now).total_seconds()
    log(f"等待到 {target.strftime('%m-%d %H:%M')} 再继续 (每日 {DAILY_LIMIT} 章分批发布)...")
    time.sleep(max(delta, 60))
    return True


def pending_count():
    """读取 state 中 status=pending 的章节数."""
    try:
        with open(STATE, encoding="utf-8") as f:
            st = json.load(f)
        chs = st.get("chapters", {})
        return sum(1 for v in chs.values() if v.get("status") == "pending")
    except Exception as e:
        log(f"  ⚠ 读取待发状态失败: {e}")
        return -1


def clear_quota_flag():
    try:
        if os.path.exists(PROG):
            with open(PROG, encoding="utf-8") as f:
                d = json.load(f)
            d.pop("quota_blocked", None)
            tmp = PROG + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            os.replace(tmp, PROG)
            log("  (已清除 quota_blocked 标记)")
    except Exception as e:
        log(f"  ⚠ 清除 quota_blocked 失败: {e}")


def main():
    if not os.path.exists(SCRIPT):
        log(f"✗ 发布脚本不存在: {SCRIPT}")
        return 1

    log("===== 自动发布循环启动 =====")
    day_no = 1
    state_fail = 0
    while True:
        log(f"===== 第 {day_no} 个发布日 =====")
        # 每日开始时刻等待 (首日可能需等到 12:00)
        now = datetime.datetime.now()
        today_start = now.replace(hour=START_HOUR, minute=START_MIN, second=0, microsecond=0)
        if now < today_start:
            delta = (today_start - now).total_seconds()
            log(f"等待到今日 {today_start.strftime('%H:%M')} 开始发布...")
            time.sleep(max(delta, 60))

        # 每日批量发布
        log(f"---- 今日发布 (最多 {DAILY_LIMIT} 章) ----")
        try:
            r = subprocess.run(
                [PY, SCRIPT, f"--daily-limit={DAILY_LIMIT}"],
                cwd=HERE,
                capture_output=False,
                text=True,
                timeout=7200,
            )
            code = r.returncode
        except subprocess.TimeoutExpired:
            log("✗ 发布超时(2h), 可能卡住, 等人工.")
            return 2
        except Exception as e:
            log(f"✗ 运行异常: {e}")
            return 2

        if code == 3:
            # 配额用尽, 清标记等明天
            log("⚠ 遇到每日字数上限, 等自然日重置后重试...")
            clear_quota_flag()
            wait_until_next_day()
            day_no += 1
            continue
        elif code == 2:
            log("✗ 发布失败(非配额), 暂停等人工.")
            return 2
        elif code != 0:
            log(f"⚠ 未知返回码 {code}, 等待 10 分钟后重试...")
            time.sleep(600)
            continue

        # code 0: 发布进程正常结束 (当日限额发完 or 全部发完)
        # 读失败(-1) ≠ 发完: 防状态文件损坏/瞬时不可读导致常驻调度误判完成而静默停摆
        pending = pending_count()
        if pending < 0:
            state_fail += 1
            if state_fail >= STATE_READ_FAIL_MAX:
                log("✗ 待发状态文件持续不可读, 退出等人工检查 (state 文件勿删).")
                return 2
            log(f"⚠ 读取待发状态失败 x{state_fail}, 视为仍有待发, 10 分钟后重查...")
            time.sleep(600)
            continue
        state_fail = 0
        if pending == 0:
            log("✓ 没有待发章节, 发布全部完成, 退出.")
            return 0
        log(f"✓ 今日已发布, 仍有 {pending} 章待发, 明天继续.")
        wait_until_next_day()
        day_no += 1


if __name__ == "__main__":
    sys.exit(main())
