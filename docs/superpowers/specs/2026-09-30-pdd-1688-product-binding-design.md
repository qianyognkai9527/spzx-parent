# 拼多多商品 ↔ 1688 货源 关联维护设计（子项目 A）

日期：2026-09-30
状态：待评审（纯设计，未落地代码）
范围：spzx-parent（Java 后端 + automation 采集）、spzx-admin（Vue 前端）。本设计是「PDD 运营闭环」三子项目中的 **A**（商品关联维护）。
关联：
- `docs/superpowers/specs/2026-09-29-multiplatform-ingest-design.md`（多平台注册表，PDD `code=3`；其 P1「数据回流」尚未落地）
- `docs/superpowers/specs/2026-09-30-pdd-wearable-nail-distribution-design.md`（`automation/pdd-auto/` 铺货，已打通）

## 1. 背景与目标

已能把淘宝穿戴甲自动铺到拼多多（`automation/pdd-auto/`）。现在要在**电商运营管理后台维护「PDD 商品 ↔ 1688 货源」的关联关系**，为后续子项目打基础：
- **B**：产生 PDD 订单后，按关联到对应 1688 货源**代发下单**；
- **C**：退货时把**退货物流单号回传 1688**。

**目标（A 范围内）**

- 把 PDD 商品导入系统（`platform_product`，`platform_type=3`）。
- 为每个 PDD 商品建立到 1688 货源的**商品级**关联（`product_bind_relation`）。
- 后台可查看/搜索/改绑/解绑该关联。

**非目标（明确不做）**

- 不做 SKU 级关联（用户已确认只做商品级；B 阶段另行处理规格对齐）。
- 不做自动匹配（标题/图去 `source_product` 猜货源）——本轮以 `铺货时补录` 为准。
- 不做 PDD 订单/售后采集（那是 B/C）。
- 不做 1688 下单、退货物流回传（B/C）。
- 不新建数据表（复用现有）。

## 2. 现状事实（本设计的依据）

- `platform_product`：`platform_type` 1=淘宝(3110 行) / 2=抖音(1569 行)，**PDD(3) 0 行**；主键 `id`，`code` 唯一（平台商品编码），有 `title/platform_type/shop_id/pricing/freight`。
- `source_product`（1688 货源）：5369 行。
- 商品级关联表 `product_bind_relation`：`product_id`(平台商品 id) ↔ `source_productId`(货源商品 id)，已有 3951 行；服务 `ProductBindRelationService`（`findUnBindSourceProduct` / `bindRelation` / `findBoundSourceProduct`）。
- SKU 级关联 `sku_bind_relation`：9 行（本期不用）。
- 前端商品关联页：`spzx-admin/src/views/mall/mallProduct.vue`（平台 tab + 「绑定货源商品」/「已关联货源商品」弹窗，走 `api/mallProduct.js` → `ProductBindRelationController`）；平台选项来自字典/平台注册表。
- 本次 4 个穿戴甲对应的**淘宝 itemId 不在 `platform_product` 中**（按 code/标题均查不到）→ 无法从「淘宝商品 → 1688 货源」自动推导。
- 淘宝商品编辑页（`item.upload.taobao.com`）**不含** 1688/货源/分销/offerId 字段（实测只有商家编码/货号）→ 1688 offerId 不能从淘宝页抓。
- 1688 ISV 铺货页（`ufuwu.1688.com`，9222，见 `sourcing/AGENTS.md`）维护着本店的铺货记录（`铺货成功`/`铺货失败` 列表，`sourcing/isv_offer_ids.json` 即取自该处）→ **1688 offerId 的来源**。

## 3. 数据链（核心）

```
pdd-auto 发布记录 ──(淘宝 itemId)──┐
                                   ├─ join → PDD商品 ↔ 1688 offerId
ISV 铺货日志(1688 offerId↔淘宝 itemId)┘
                                   │
                        source_product(按 1688 offerId)
                                   │
        platform_product(type=3) + product_bind_relation
```

三步：
1. **ISV 铺货日志**（9222）抓 `(1688 offerId, 淘宝 itemId)` → `isv_offer_taobao_map.jsonl`。
2. **pdd-auto 发布记录**：铺货成功时记 `(pdd goods_id, 淘宝 itemId, 标题, 价格, 图)` → `pdd_products.jsonl`（增强 `create_pdd_product.py`）。
3. **join + 导入**：用 淘宝 itemId 串起 1、2；用 1688 offerId 在 `source_product` 找到 `source_product.id`；upsert `platform_product(3)` 与 `product_bind_relation`。

## 4. 设计决策

| 编号 | 决策 | 理由 |
|---|---|---|
| A-D1 | 只做商品级关联，复用 `product_bind_relation` | 用户明确；SKU 级留 B |
| A-D2 | 不新建表；`platform_product`/`product_bind_relation` 沿用 | 现有结构已够，符合 09-29 spec「不建平行表」 |
| A-D3 | 导入走 Python 脚本（对齐现有直写习惯），Java 仍是表结构 owner | 采集侧在 automation，导入天然在 Python |
| A-D4 | 关联来源 = ISV 铺货日志 join pdd-auto 记录，不猜 | 用户确认「铺货时补录」，1688 id 来自 ISV |
| A-D5 | 后台维护复用 `mallProduct.vue` + `ProductBindRelation` 三接口，仅加 PDD(3) 维度 | 现有功能已满足，只差平台 |
| A-D6 | 幂等：以 PDD `goods_id` 为键 upsert | 重复导入不产生脏行 |

## 5. 数据模型

复用，无 DDL：

- `platform_product`：`code`=PDD `goods_id`，`platform_type=3`，`title`、`pricing`(=PDD 拼单价)、`shop_id`(PDD 店)。
- `product_bind_relation`：`product_id`=上面 `platform_product.id`，`source_productId`=`source_product.id`（由 1688 offerId 解析）。

## 6. 采集与导入脚本（`automation/`）

| 脚本 | 位置 | 作用 |
|---|---|---|
| `scrape_isv_offer_taobao.py` | `sourcing/` | 读 ISV 铺货成功/全部列表，抓 `(offerId, 淘宝 itemId)` → `isv_offer_taobao_map.jsonl` |
| （增强）`create_pdd_product.py` | `pdd-auto/` | 提交成功时记 `pdd_products.jsonl`：`pdd goods_id / 淘宝 item_id / title / price / images` |
| `build_pdd_bind_worklist.py` | `pdd-auto/` | 纯函数 join：pdd 记录 × ISV 映射 × source_product → 待写关联 |
| `import_pdd_products.py` | `pdd-auto/` | upsert `platform_product(3)` + `product_bind_relation`（幂等） |

## 7. 后台维护 UI（`spzx-admin`）

- `mallProduct.vue` 平台 tab 增加 **拼多多**（由平台注册表 `platform` 驱动；09-29 spec 已验证启用 `code=3` 后 tab 自动出现）。
- 列表展示 PDD 商品（标题/价格/店铺）+ 已绑 1688 货源；支持「绑定货源商品」搜选、改绑、解绑。
- 复用现有弹窗与 API，不新建页面。

## 8. 后端（`spzx-manager`）

- `ProductBindRelationService` 三接口确保在 `platform_type=3` 下正确（`findUnBindSourceProduct` 按平台/店铺过滤未绑货源；`bindRelation` 落库；`findBoundSourceProduct` 读已绑）。
- 平台/店铺维度优先走 09-29 spec 的 `PlatformRegistryService`（`platform` 表 code=3）与 `shop` 表；PDD 默认店需存在（`shop` 表补一行 PDD 店，`ingest_channel=browser`）。
- **不新增表、不新增 controller**（复用）。

## 9. 测试

- 纯 JUnit / 纯 assert（仓库风格）：join 逻辑（淘宝 itemId 缺失、1688 offerId 无对应 `source_product`、重复 goods_id 幂等）。
- 后端：`ProductBindRelationService` 在 platform_type=3 下的查询/绑定（MyBatis 层或轻量单测）。

## 10. Phase 0（spike，先行）

1. 打开 ISV 铺货成功/全部列表（9222），确认每行**含淘宝 itemId**（若只有 offerId，需点进详情确认可拿 itemId）。→ 决定 `scrape_isv_offer_taobao.py` 可行性。
2. 改 `create_pdd_product.py` 成功时写记录，并**回填已上架的 4 条**（从提交成功 URL 的 `goods_id` + worklist 的 `item_id`）。
3. 跑通 4 条端到端导入，后台 PDD tab 能看到并已绑定。

## 11. 分期与退出条件

| 阶段 | 内容 | 退出条件 |
|---|---|---|
| Phase 0 | spike ISV 映射 + 补记录 + 回填 4 条 | ISV 能拿到 itemId；4 条导入成功 |
| Phase 1 | `import_pdd_products.py` + 后端 platform=3 生效 | 后台 PDD tab 列出并可见关联 |
| Phase 2 | 前端绑定/改绑/解绑可用 | 人工改绑一条并生效 |
| Phase 3（可选） | 接入 B/C | 另立 spec |

## 12. 风险与未决

1. **ISV 铺货日志是否含淘宝 itemId**：Phase 0 回填。若不含，需从 offer 详情页或 ISV 接口取，成本上升。
2. **1688 offerId → source_product 是否收录**：ISV 里的 offer 未必都在 `source_product`（那是选品采集来的）。缺失时该关联只能留空待人工，需在导入报告里列出缺失清单。
3. **PDD 店铺归属**：`shop` 表需有 PDD 店（`platform_code=3`）；否则 `platform_product.shop_id` 为空，看板/利润口径后续要处理。
4. **淘宝 itemId 重复铺货**：同一 1688 offer 可能对应多条淘宝/PDD 记录，join 需定义去重口径（按 PDD goods_id 唯一）。
5. 平台注册表 `platform`/`shop` 若尚未落地，A 的「PDD tab」需先补种子（09-29 spec 已设计，未确认执行）。

## 13. 实施修订（2026-10-01，实现期纠正）

实现时发现原设计两处与实际不符，按事实修正：

1. **数据源改为 ISV「商品管理」菜单，不用「铺货日志」**。理由：
   - 「铺货日志」默认日期仅近一周，且行内只有 1688 offerId、**没有淘宝 itemId**；靠点「编辑店铺商品」跳淘宝页取 itemId，行/按钮配对易错位（实测同一 item 得到过错误号码）。
   - 「商品管理」**一行同时含 店铺商品ID(淘宝 itemId) 与 货源商品ID(1688 offerId)** + 货源名/价/供应商，无需点开任何页面 → 可靠且不开新标签。
   - 采集脚本 `sourcing/scrape_isv_offer_taobao.py` 走「商品管理」，支持 `--ids` 精查（1 页出结果）。
2. **1688 货源不在 `source_product` 时，导入期自动建行**（用户确认）：
   - `source_product`：`source_product_code`=offerId，`source_product_name`=货源名，`source_price`=货源价，`supplier_name`=供应商，`platform_type=1`。
   - 之后 `platform_product(platform_type=3, code=PDD goods_id)` 与 `product_bind_relation` 绑定。
3. **实测已入库 4/4**（第 4 个为草稿箱态，goods_id 已从 PDD 草稿箱取到）：

| 淘宝 itemId | PDD goods_id | 1688 offerId | 货源价 | PDD 状态 |
|---|---|---|---|---|
| 1077395263073 | 1011567189435 | 1055031942046 | 16.5 | 在售 |
| 1080310116827 | 1011567407564 | 1055029950080 | 14 | 在售 |
| 1079306693060 | 1011567730156 | 1054239797138 | 17 | 在售 |
| 1077394579345 | 1011566567489 | 1054196945875 | 14 | 草稿箱（未上架；另有重复草稿 1011564103589） |

4. **`create_pdd_product.py` 已改**：提交成功时落盘 `pdd_products.jsonl`（含 `goods_id`），后续铺货自动带 id，无需手工回填。
5. **平台启用**：`platform` code=3 `enabled=1`、`shop` id=3 `status=1` 已执行（前端 PDD tab 由注册表驱动）。
