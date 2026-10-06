# 淘宝「睡衣/家居服」批量改品牌 + AI 导购标题 + AI 新主标题 — 设计文档

日期：2026-10-05
状态：已确认（用户批准设计与失败策略）

## 背景

淘宝默认店（shop_id=1，CDP 9222）里「睡衣/家居服」店铺分类的商品，品牌杂、标题带 1688 痕迹、缺少导购标题。需要批量统一品牌为「瑰若」，并借平台 AI 重做导购标题与商品主标题，提升搜索与转化。

仓库已有可复用资产：

- `assign_shop_category_v2.py`：批量编辑骨架——打开编辑页、`wait_edit_ready`、`clear_overlays`、`handle_recommend_dialog`、保持上/下架状态、`click_submit`、进度合并（fcntl 锁）、风控 `exit 42`。
- `_archive_20260906/edit_jeans_batch.py`：已验证的字段填充手法——品牌下拉 React fiber `fill_select`；导购标题 AI（清空 `#sell-field-shopping_title` 内 input → 点 `.ai-icon` → 等「立即使用」→ 点击）。
- `collect_in_stock_current.py`：列表页 `SellManage/{in_stock,sold_out}` 翻页采集 itemId+标题。

## 目标与范围

- **店铺**：淘宝默认店（9222，提交类必须**窗口模式** Chrome）。
- **圈选**：商品管理列表页用**店铺分类筛选 = 睡衣/家居服**（不按标题关键词猜），**出售中 + 仓库中**两个 tab 全都要。
- **每件操作**（顺序固定，用户指定）：
  1. 品牌 → `瑰若`
  2. 导购标题 → 平台 AI 生成并采纳（基于**现有**主标题）
  3. 商品主标题 → 平台 AI 生成并采纳，**必须以「瑰若」开头**
  4. 提交，**维持原上/下架状态**；不动价格、不动店铺分类。
- **不做**：不存回滚数据（用户确认不需要）；不改价格/类目；不处理非此类目商品。

## 用户已确认的决策

| 项 | 决策 |
|---|---|
| 平台 | 淘宝默认店（非抖店） |
| 范围 | 出售中 + 仓库中，全都要 |
| 顺序 | 品牌 → 导购标题 AI → 新主标题 AI（**不改顺序**，因商品当前已有标题） |
| 品牌 | 「瑰若」在品牌下拉中可选 |
| 新主标题前缀 | 前两个字必须是「瑰若」（AI 结果未带则前置补齐） |
| 回滚 | 不需要 |
| AI 失败策略 | 导购标题或新主标题 AI 失败 → **整件标 `failed` 不提交**，下轮 `--retry-failed` 重试，避免半成品 |
| 探路 | 允许先 `--test` 在样本上把选择器补全，再全量 |

## 设计

### 1. 圈选：`enumerate_targets(page)` → `brand_title_targets.jsonl`

- 分别在 `SellManage/sold_out`（出售中）与 `SellManage/in_stock`（仓库中）页面：
  - 展开「店铺分类」筛选下拉，选中「睡衣/家居服」（**Phase 0 确认真实文本，可能是「家居服/睡衣」**）。
  - 点「搜索」，翻页（点「下一页」按钮，`goto ?current=N` 无效），复用 `collect_in_stock_current.extract_items` 提取 `{itemId, title}`。
  - 每行记 `pool: onsale|warehouse`。
- 断点续跑按 itemId 去重；输出 `brand_title_targets.jsonl`（每行 `{itemId, title, pool}`）。
- 该 JSONL 即本任务权威清单（替代 `shop_cat_plan.json` 的标题关键词判定）。

### 2. 单件流程：`process_one(ctx, rec)`

编辑页 URL 沿用 v2：`https://item.upload.taobao.com/sell/v2/publish.htm?itemId={id}&fromAIPublish=true`。

```
page = ctx.new_page()  # 每件新开 tab（SPA 同 URL goto 不重渲染）
goto(EDIT_URL)
title = wait_edit_ready(page)          # 等表单水合；失败 → fail
handle_recommend_dialog(page)          # 属性推荐弹框「确定」
scroll_edit_page(page); clear_overlays(page)
check_listing_mode(page)               # 必须 ∈ {放入仓库, 立刻上架}，否则 fail
set_brand(page, '瑰若')                 # 见 2.1
ai_guide_title(page)                   # 见 2.2
ai_main_title(page, prefix='瑰若')      # 见 2.3
click_submit(page)                     # 复用 v2；风控 → risk
```

#### 2.1 品牌：`set_brand(page, '瑰若')`

抄 `edit_jeans_batch.fill_select`：按 label「品牌」定位 `sell-component-info-wrapper-wrap` → React fiber 取 `dataSource` 里 `text === '瑰若'` 的项调 `onChange`；fallback 走 UI 点选（hover 清除 → 点开下拉 → 点匹配项）。写回校验 `.next-select-values em` 文本 == 瑰若；选不到 → 返回 fail。

#### 2.2 导购标题 AI：`ai_guide_title(page)`

抄 `edit_jeans_batch.fill_ai_guide_title`：

1. 定位 `#sell-field-shopping_title, [id*="shopping_title"]`，native setter 清空 input（有值时 AI 不触发）。
2. 点 wrapper 内 `.ai-icon`。
3. 轮询 ≤15s 等「立即使用」（`.adopt-btn, span` has_text），可见即点击。
4. 超时未出现 → 失败。

#### 2.3 新主标题 AI：`ai_main_title(page, prefix='瑰若')`

**Phase 0 主要未知点**：主标题旁的平台 AI 按钮选择器（导购标题是 `.ai-icon`，主标题那个待探路确认）。

- 点主标题 AI 按钮 → 等生成 → 采纳（具体按钮/弹层选择器在 `--test` 探路时补全并回写本节）。
- 采纳后读回主标题 input 值：
  - 若不以「瑰若」开头 → 前置「瑰若」（若原值已含「瑰若」但不在开头，先去掉原位置的「瑰若」再前置，避免重复）。
  - 截断到平台标题上限（暂按 30 汉字；探路确认真实上限）。
- 生成超时/按钮找不到 → 失败。

#### 2.4 提交

`click_submit(page)`（复用 v2）：新开浮层处理逻辑一致；`risk` → 主循环保存进度 `exit 42`；`超时未确认` 假失败 → 重开编辑页读回品牌=瑰若且主标题以「瑰若」开头，成立则判 ok，否则判 failed 待重试。

### 3. 进度与失败：`brand_title_progress.json`

结构：`{ "done": [itemId...], "failed": {itemId: {error, pool, oldTitle?}}, "skipped": [itemId...] }`。
（`oldTitle` 仅记录用于排查，不作为回滚用途。）

- `done`：品牌=瑰若 + 导购标题非空 + 主标题以瑰若开头 + 提交成功。
- `failed`：任一步失败（品牌选不到、AI 超时、提交失败）→ 不提交，留待 `--retry-failed`。
- `skipped`：数据问题（编辑页打不开、商品已消失/状态异常）不自动重试。
- 保存沿用 v2 的 fcntl 锁 + 磁盘合并。

### 4. 风控与节奏

- 提交类必须**窗口模式** Chrome 9222（headless 必被 RGV587 拦）。
- 触发风控（RGV587/x5sec/滑块）→ 保存进度 `exit 42`。
- 节奏参考 v2：每件间隔 3-5s，每 30 件休息 25-35s；AI 生成额外等待。
- 包装脚本 `run_brand_title.sh`：循环调用，`exit 42` 时冷却阶梯（20m→40m→2h 封顶）后自动续跑；非 0 且非 42 退出停止并报警。

### 5. CLI 参数

```
edit_brand_title_batch.py
  --test            只处理 1 件（探路/验收）
  --limit N         处理 N 件
  --start N         从清单第 N 条起
  --retry-failed    只重试 failed
  --ids id1,id2     定向处理（可补跑 skipped；done 仍跳过）
  --enumerate       只采集清单，不进编辑页
```

## Phase 0 探路（先于全量）

在 1-2 个真实样本上确认并回写本 spec：

1. 「店铺分类」筛选下拉：容器选择器、选项文本（睡衣/家居服 vs 家居服/睡衣）、搜索/重置按钮。
2. 主标题 AI 生成按钮：容器、触发后弹层/候选列表结构、「采纳/立即使用」按钮。
3. 品牌下拉是否含「瑰若」，写回校验方式。
4. 主标题字段长度上限、是否与导购标题互斥。
5. 导购标题 AI 是否受主标题长度/内容影响。

若主标题 AI 确实不存在或不可用 → 暂停并回报用户，不擅自换方案。

### 结论（2026-10-05 探路，实测 dump 于 `probe_brand_title_out.json`）

- **店铺分类筛选**：选项真实文本 = **「家居服/睡衣」**；筛选区需先点「展开」→ `input#queryShopCategoryId` 的 `.next-select`；选项节点 `.next-tree-node-label.next-tree-node-label-selectable`（tree-select）。
- **主标题 AI 触发 = `#sell-field-title .ai-icon`**（存在，探针确认可见）。
- **导购标题 AI = `#sell-field-shopping_title .ai-icon`**；注意页面另有外层 `#struct-shopping_title` 会抢 `[id*=shopping_title]`，定位**必须优先 `#sell-field-shopping_title`**。
- **品牌字段容器 = `#sell-field-p-20000`**；但品牌下拉是**虚拟列表**，fiber `dataSource` 只挂载前 50 项且样品当前品牌已=瑰若，故 `set_brand` 不能只靠 fiber，**必须有展开下拉+滚动加载后再点的兜底**。
- **标题上限 = 30 汉字 / 60 字符**（页面 placeholder 实写），`TITLE_MAX=30` 正确。

## 验收

- `--test` 1-2 件：回列表/编辑页确认 品牌=瑰若、导购标题非空、主标题以「瑰若」开头且已提交生效。
- 小批（如 10 件）确认成功率与风控节奏。
- 全量结束：目标清单数 = done + failed + skipped；failed/skipped 单独列明原因，可 `--retry-failed` 收敛。

## 交付物

- `automation/sourcing/edit_brand_title_batch.py`（新脚本，不改 `assign_shop_category_v2.py`）。
- `automation/sourcing/run_brand_title.sh`（冷却续跑包装）。
- `automation/sourcing/brand_title_targets.jsonl` + `brand_title_progress.json`（运行期产物，gitignore 覆盖）。
- 更新 `automation/sourcing/AGENTS.md`：记录本任务坑位（筛选下拉文本/主标题 AI 选择器/风控节奏）。

## 非目标

- 不改价格、不改店铺分类、不改 SKU/图片。
- 不处理「睡衣/家居服」以外的类目。
- 不做回滚工具。
