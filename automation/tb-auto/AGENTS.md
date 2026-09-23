# AGENTS.md

Browser automation (Python 3.9 venv + Playwright async API) that re-lists failed 1688→Taobao product drafts: sets price ×3, selects store category 家居服/睡衣, sets 上架时间=放入仓库, enables 商品预检, generates a compliant 款号, and submits to warehouse. Progress persists across runs for breakpoint resume. NOT a git repo - don't run git commands here.

## Environment / Chrome (critical)

- Chrome must already be running with CDP before any script runs:
  ```bash
  arch -arm64 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir="/Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto/chrome-profile" \
    --no-first-run "https://ufuwu.1688.com/page/fuwu_work_isv_container.htm?appkey=2839818"
  ```
- Chrome 150+ refuses `--remote-debugging-port` with the default profile — you MUST use a non-default `--user-data-dir` (the `chrome-profile` dir holds the 1688 login).
- Use `arch -arm64` prefix: the default shell runs under Rosetta (x86) and launching Chrome without it is extremely slow.
- Do NOT close/reopen the browser during a run; it raises risk-control flags.

## Run commands

```bash
cd /Users/qyk9527/ideaProject/spzx-parent/automation/tb-auto
nohup venv/bin/python3 auto_list.py > batch.log 2>&1 &   # full batch (resumes from progress.json)
venv/bin/python3 auto_list.py --test                     # process an already-open edit page, no submit
venv/bin/python3 auto_list.py --limit N                  # process at most N products
```

Flags are parsed from `sys.argv` in `auto_list.py`'s `__main__` (no argparse) - add new flags there.

## Prerequisites before running

- User must MANUALLY click "铺货日志" in the 1688 sidebar and select the 铺货失败 tab first. The Ant Design SPA menu CANNOT be navigated by script clicks — the batch only works if the 铺货日志 page is already open. (Deletion scripts `delete_adult*.py` navigate pages themselves.)
- Content lives in the iframe whose URL contains `isv-container` (Ant Design). Taobao edit page is `item.upload.taobao.com` (Next UI; fields use `sell-field-*` / `struct-*` IDs).

## Behavior / gotchas

- **款号 rule** (`rules.py:generate_style_number`): 2 uppercase letters + 3 digits; first digit must NOT be 4; no "38" substring.
- **Operation order**: 价格×3 -> 店铺中分类=家居服/睡衣 -> 上架时间=放入仓库 -> 商品预检. The 商品预检 checkbox is only enabled AFTER 放入仓库 is selected (code marks this 关键).
- **Two-tier submit**: first `do_submit` runs with the minimal ops above. If it fails for ANY reason (not a specific error message), `fill_category_attributes` fills empty required category attributes from a title-aware `attr_rules` dict, then resubmits.
- **Slider (阿里云滑块)**: triggered by rapid operations / attribute filling. Detection is size-aware (`#nc_1_wrapper` etc., >150×30). 三种行为: (a) 编辑页处理中触发 → 该商品标记 failed 继续; (b) **ISV 铺货日志页触发 → 保存 progress 并整个退出 batch**（不会继续）; (c) 提交后 verify_submission 触发 → **最多等 10 分钟人工过验证**再重试提交。运行中需要人去 9222 Chrome 手动拖滑块。
- **Shop-restriction permanent skip**: 情趣内衣/成人-category products ALWAYS fail with "成人类目市场为专营制" (store lacks adult-market qualification). These are added to `processed` so they are never retried — do not treat as retryable.
- **Progress** (`progress.json`): `processed` (list of row_keys, includes permanently-skipped) + `failed` (list, retried next run) + `count` (= len(processed)). `session_failed` is an in-memory set that resets each run - it only prevents same-run infinite retry and is NOT persisted. Do not lose this file — it is the only resume state.
- **价格×3** (`auto_list.py` ~L183): 一口价 and SKU prices ×3. `base_price` defaults to `1.01` when the original 一口价 is ≤0 or unparseable. SKU inputs whose value has no decimal point are skipped (they're stock counts, not prices); 0-price SKUs get the ×3 `base_price`, not left at 0.
- **Timing / batch breaks** (`config.py`): 8-15s between products (`MIN_DELAY=8, MAX_DELAY=15`). Every 80 products pauses 2-3 min (`BATCH_50=80`, break 120-180s); every 400 products pauses 10-15 min (`BATCH_200=400`, break 600-900s). A full batch runs for hours - a long pause is expected, not a hang.
- **"处理完成"≠全部清完**: batch 边处理边删铺货日志条目导致分页错位、会漏采; 日志写"已到第一页,没有更多页面了"时可能仍剩几百条在铺货失败列表。重跑前/后必须用 CDP 读 ISV 铺货失败 tab 的 `共 N 条` 和 `progress.json` 对账, 数值不降就继续跑。

## Maintenance scripts (all in repo)

- `delete_adult3.py` — delete remaining 情趣内衣 products from the failed list (ADULT_KEYWORDS: 情趣, 圣诞装, 制服, 角色扮演, 兔女郎, 丁字裤, 开裆, 免脱, 三点, 女仆, 连体衣, 绳衣). Set list to 100条/页 first via `.ant-pagination-options-size-changer` for speed.
- `scan_adult.py` — scan all pages, count remaining adult products (run to verify deletion is complete).
- `rules.py:infer_attributes` is imported by `auto_list.py` but NEVER called - dead code; real attribute inference lives inline in `fill_category_attributes`.
- Many `inspect_*` / `diagnose_*` / `test_*` scripts are one-off debugging tools; `auto_list.py`, `rules.py`, `config.py` are the real code.
