#!/usr/bin/env bash
# 启动 Chrome 9223 (sourcing 选品用) - headless无窗口
arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9223 \
  --user-data-dir="/Users/qyk9527/ideaProject/spzx-parent/automation/sourcing/chrome-profile-sourcing" \
  --no-first-run \
  --headless=new \
  --disable-extensions \
  --disable-gpu \
  --disable-features=TranslateUI,site-per-process \
  --disable-background-timers \
  --disable-backgrounding-occluded-windows \
  --disable-background-networking \
  --renderer-process-limit=6 \
  --js-flags="--max-old-space-size=512"
