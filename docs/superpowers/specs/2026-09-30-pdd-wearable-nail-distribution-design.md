# 淘宝穿戴甲 → 拼多多铺货设计

日期：2026-09-30
状态：待评审（纯设计，未落地代码）
范围：新增 `automation/pdd-auto/` 一套 Python 铺货流水线。**不涉及 Java 后端与前端**（落 DB / 接多平台注册表列为二期）。
关联：`docs/superpowers/specs/2026-09-29-multiplatform-ingest-design.md`。那份设计把拼多多定义为 `code=3`，第一波**只做数据回流（订单/售后/商品/日指标/推广，只读）**，明确"不做写动作"。本设计是其之外的**新增写动作**（把淘宝商品铺到 PDD），二者数据方向相反、互不替代。

## 1. 背景与目标

把指定淘宝穿戴甲商品自动铺到拼多多「穿戴甲」类目商家后台，常态持续上新。

**目标**

- 人工指定一批淘宝商品 → 自动采集 → 映射 → 在 PDD 商家后台发布。
- 常态跑：断点续跑、幂等去重、失败重试。
- 价格：淘宝价 ×1.3（整店统一，不做区间分档）。

**非目标（明确不做）**

- 不做自动差异选品：不做"淘宝有、PDD 没有"的自动扫描，一律人工指定商品。
- 不做订单/售后/库存回传（那是 09-29 PDD 设计的 P1）。
- 本期不做 1688 直采（后续可加，采集器可替换）。
- 不落 DB、不接多平台注册表、不改 Java/前端（二期 C）。
- 不做 PDD 开放平台 API 接入（本期走浏览器自动化；API 作为探路失败的退路之一）。

## 2. 已确认前置事实

- 拼多多店已开，**类目=穿戴甲**，可登录商家后台 `mms.pinduoduo.com`。
- 商品数据源：**淘宝店铺千牛后台网页版**（后续可切 1688）。
- 触发方式：**人工指定**要铺的淘宝商品（不做自动增量）。
- 规模与频率：**常态持续上新**（不是一次性搬迁）→ 必须有断点续跑/幂等/批量循环。
- 价格：**淘宝价 ×1.3**，整店统一。
- 现有自动化生态：Playwright async + CDP；端口 9222=tb-auto（淘宝/1688）、9223=sourcing（抖店/1688）；统一 `automation/venv/bin/python`（Python 3.9）。

## 3. 总体架构与目录

新建 `automation/pdd-auto/`，与现有平台线隔离。

| 文件 | 职责 |
|---|---|
| `pdd_config.py` | 端口 9224、profile 路径、×1.3 系数、PDD 类目/属性映射表、文件路径 |
| `run_chrome_pdd.sh` | **窗口模式**起 Chrome 9224 + 独立 profile（`pdd-auto/chrome-profile`，扫码登录一次） |
| `collect_qianniu.py` | 千牛网页版采集指定商品 → `taobao_product_data.jsonl` |
| `build_pdd_worklist.py` | 纯函数：PDD 类目/属性/SKU 映射 + ×1.3 → `pdd_worklist.jsonl`（可单测） |
| `create_pdd_product.py` | PDD 商家后台发布，断点续跑，写 `pdd_create_progress.json` |
| `run_pdd_all.sh` | 冷却循环 wrapper（风控阶梯，仿 `sourcing/run_isv_republish.sh`） |
| `AGENTS.md` | 本目录坑位（探路后回填） |

约定：

- **端口不混**：采集走既有淘宝/千牛登录（复用 9222 的淘宝 profile）；**发布独立 9224 + 独立 profile**，避免与 9222/9223 混端口（全局红线）。
- 复用 `sourcing/cdp_utils.py`（`sys.path` 引用其目录，不改现有代码）；`connect_cdp(9224, keep_urls=[...pinduoduo...])`。
- Chrome 必须 `arch -arm64`；窗口模式（PDD 后台提交类），不带 `--headless`/`--disable-gpu`。
- 数据/登录态（`chrome-profile*`、`*.jsonl`、progress）沿用现有 `.gitignore` 规则，勿提交。

## 4. 数据契约

**`taobao_product_data.jsonl`**（采集产物，每行一个商品）

```
{"item_id": ..., "title": ..., "main_images": [...], "detail_images": [...],
 "skus": [{"spec": ..., "price": ..., "stock": ...}],
 "price_min": ..., "price_max": ..., "code": ..., "collected_at": ...}
```

**`pdd_worklist.jsonl`**（映射产物）

```
{"item_id": ..., "pdd_category": "穿戴甲", "title": ..., "attributes": {...},
 "skus": [{"spec_value": ..., "price": ..., "stock": ..., "img": ...}],
 "images": [...], "status": "todo"}
```

**`pdd_create_progress.json`**（台账）

```
{"done": [item_id...], "failed": {"item_id": "reason"}, "skipped": [item_id...],
 "updated_at": ...}
```

去重键统一用淘宝 `item_id`：`todo = 指定列表 − done`（`failed` 由 `--retry-failed` 放行）。

## 5. Phase 0 探路（最大风险，先行）

PDD `mms.pinduoduo.com` 反自动化强弱未知，是整件事能否成立的前提。**先探路，再写正式脚本。**

- 窗口模式登录 PDD 商家后台，手动在「穿戴甲」类目走一遍商品发布。
- dump 发布页：字段结构、必填项、SKU/规格控件类型、图集/白底图要求、类目属性、提交入口、是否有验证码/滑块。
- 验证两件事：**CDP 能读到字段 + 能用脚本提交成功一次**。
- 探路结果回填本目录 `AGENTS.md` 与本文档「未决项」。
- **退出条件**：单商品可脚本化发布成功（或明确风控阻挡，转退路）。**探路失败 → 退回第三方铺货工具或 PDD 开放平台 API。**

## 6. 风控与错误处理

- 验证码/滑块检测：单商品标记 `failed` 继续；若在列表页/关键节点触发，保存进度并整批退出冷却（阶梯 20m→40m→2h 封顶）。
- 降速：商品间隔、每 N 个长休息（参照 `sourcing` 现有节奏）。
- 失败重试：`--retry-failed` 只重试 `failed`；数据问题（属性/规格缺失、无版权图）标 `skipped` 不自动重试。

## 7. 幂等 / 续跑 / 去重

- `create_pdd_product.py` 启动读 `pdd_create_progress.json`，跳过 `done`。
- 每处理完一个立即落盘（崩溃/冷却可断点续跑）。
- 重复指定同一淘宝商品（已 `done`）直接跳过。

## 8. 测试策略

沿用仓库 Python 风格（**无 pytest**，纯 `assert` 脚本，如 `sourcing/test_bc_rules.py`）：

- 价格 ×1.3 计算（含分/四舍五入、SKU 价统一乘）。
- 类目/属性/SKU 映射纯函数。
- worklist 生成与去重逻辑。

## 9. 分期与退出条件

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| Phase 0 | 探路 spike | 单商品可脚本化发布，或确认不可行转退路 |
| Phase 1 | 采集 + 映射 + 单商品发布 | 端到端铺成功 1 个穿戴甲 |
| Phase 2 | 批量 / 续跑 / 风控 / wrapper | 批量铺 N 个、断点续跑验证、冷却可用 |
| Phase 3（可选） | 落 DB（`platform_product` platform_type=3）/ 接多平台注册表 | 与 09-29 设计合流 |

## 10. 风险与未决项（探路回填）

1. **PDD 后台自动化可行性**（最大）：字段/提交能否脚本化、验证码频率——Phase 0 回填。
2. 登录态：新 profile 需扫码一次；窗口模式；登录过期需重登。
3. 图源版权：来自千牛的自有图应无盗图问题；若沿用 1688 供应商图，PDD 端同样有盗图/重复铺货风险（淘宝侧当前卡点即 `PIC_STEAL`）。需确认图源策略。
4. 价格/库存与淘宝的同步口径（本期不做回传，铺后价格是否会在 PDD 侧被改由人工处理）。
5. PDD 穿戴甲类目每店发布量/风控配额未知，探路时观察。
6. 采集侧：千牛商品详情页字段能否稳定抓到（SKU/详情图），需在 Phase 1 验证。
