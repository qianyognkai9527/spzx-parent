# 淘宝美甲（穿戴甲本体）→ 拼多多 1688 直铺 · 预准备与执行设计

日期：2026-10-08
状态：已与用户确认，进入执行
范围：`automation/pdd-auto/` 现有 1688 直铺线上的一次「全量穿戴甲本体」铺货准备 + 当晚执行。**不涉及 Java 后端/前端**。
关联：
- `automation/pdd-auto/AGENTS.md`（发布闭环坑位、合规闸门、定价 ×5、店铺对账）
- `docs/superpowers/specs/2026-09-30-pdd-wearable-nail-distribution-design.md`
- `docs/ECOMMERCE_RULES.md`（划线价/品牌管控）

## 1. 目标与范围

- 把 `automation/sourcing/1688_meijia_worklist.jsonl` 里的**穿戴甲本体**全部预备成可发布的 PDD 队列，当晚一键开跑。非穿戴本体（工具/胶/钻/收纳）**不铺**。
- 货源 = 1688 直铺（复用现有 `run_pdd_1688.sh` 线）；拼单价 = 进价 × `PRICE_FACTOR_1688`(5.0)；类目 `彩妆/香水/美妆工具 > 指甲贴/穿戴甲 > 手工穿戴甲`。
- **准备阶段不发布**；用户当晚说「开始」才启动发布 wrapper。

## 2. 前置准备（离线 / 只读）

| 步骤 | 命令 | 说明 |
|---|---|---|
| P1 合规词表自检 | `../venv/bin/python sync_compliance_rules.py --check` | 漂移则 `sync_compliance_rules.py` 同步进仓 |
| P2 店铺对账 | `../venv/bin/python sync_pdd_store.py`（需 9224 窗口模式） | 刷新在售快照 + 累积驳回台账 `pdd_rejections.json`；新品牌词只**提名**，不自动拉黑 |
| P3 全量重建队列 | `../venv/bin/python build_pdd_worklist_1688.py`（无 limit） | 穿戴本体过滤 + 最新品牌/合规 + 复用 `pdd_images_1688/` 缓存、缺图补下 |
| P4 去重 | 剔除「已在 PDD」的 offerId（`pdd_products.jsonl` 的 `item_id` ∪ `PROGRESS_1688.done`） | 避免重复铺 |
| P5 闸门自检 | `../venv/bin/python create_pdd_product.py --source 1688 --preflight` | 连浏览器前拦；应 0 未预期命中 |
| P6 登录核验 | `create_pdd_product.py --source 1688 --test` 或打开 9224 首页 | `chrome-profile` 登录态；失效需窗口模式扫码（唯一人工项） |

## 3. 当晚执行

用户说「开始」→ 启动 `run_pdd_1688.sh`：
- 每轮前 `ensure_chrome`（9224 掉线自动重启）
- `create_pdd_product.py --source 1688`（按 `pdd_create_progress_1688.json` 跳过 done）
- 每轮收尾自动 `sync_pdd_store.py` → `import_pdd_products.py` → `audit_pdd_catalog.py`
- 风控(退出码 42) 冷却 30m→60m→120m 封顶；验证码第 2 次隔离、连续 3 件退出冷却

## 4. 去重 / 失败 / 节奏

- done 跳过；`--retry-failed` 补跑失败；验证码第 2 次隔离（`CAPTCHA_QUARANTINE_AFTER=2`）；连续 3 件验证码 = 账号级风控退出冷却。
- 间隔 `ITEM_GAP_SEC=25`。

## 5. 验收

- P3 后：队列条数 = 穿戴本体筛选后条数；抽查若干条图存在且短边 ≥480px。
- P5：闸门无未预期命中（命中即列出）。
- 当晚跑完：店铺在售增长与 done 吻合；驳回只可能品牌词（对账台账可查）。

## 6. 非目标

- 不铺非穿戴本体（工具/胶/钻/收纳）；改口径需另议。
- 不改 ×5 价格口径与 `REF_PRICE_FACTOR`（划线价属经营决定）。
- 不动 Java 后端 / Vue 前端；不做自动选品（只按人工给定的 1688 货源清单）。
