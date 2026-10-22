# AI 智能客服产品设计（Chatwoot 壳 + Java AI 大脑）

日期：2026-10-09
状态：设计已逐节评审通过；本 spec 待用户审阅（**未提交 git —— 用户明确「不要执行任何 git 提交」**）
范围：Phase A（自用单租户）为本次实现范围；Phase B/C 为演进路线，不在本次实现范围

## 1. 背景与目标

用户希望基于两个开源项目做出一个 **AI 客服产品**：

- [Chatwoot](https://github.com/chatwoot/chatwoot)：成熟的开源客服工单/全渠道收件箱（Intercom/Zendesk 替代），Ruby on Rails + Vue，37.6k★，**MIT**（`enterprise/` 目录除外）。
- [TGO](https://github.com/tgoai/tgo)：新的「AI Agent 客服平台」，Python/FastAPI 微服务 + React，627★，**修改版 Apache-2.0**（禁止多租户、禁止改前端 LOGO，SaaS 需商业授权）。

**目标**：做一个既能**自用**（自家淘宝/抖音/拼多多店铺买家客服）又能**对外做 SaaS** 的 AI 客服产品。
经逐节评审，最终形态为：

> **Chatwoot 黑盒当「壳」+ 自建 Java「AI 大脑」+ Python「渠道侧车」+ 独立只读对接 spzx。**
> 壳与大脑两端都做成**可替换**（双 Port + 统一会话模型），以便后续接入其他 AI 项目、逐步平替 Chatwoot。

**交付形态**：Phase A（单租户自用）→ Phase B（多租户 SaaS）→ Phase C（电商 AI 员工/运营中枢）。

## 2. 需求决策（已与用户确认）

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 产品定位 | **自用 + 对外 SaaS 都要**；故采「先垂直自用、再 SaaS」的 A→B→C 顺序 |
| 2 | 核心场景 | 电商垂类客服（先）+ 通用 AI 客服平台 + 电商 AI 员工，**共用一套 AI 内核**，分阶段实现 |
| 3 | 起步阶段 | **A→B→C**：先自家电商客服闭环（单租户、不踩许可证），再抽成多租户 SaaS |
| 4 | 渠道接入 | **原生（网页/微信）→ 抖店官方 API → 淘宝/拼多多浏览器自动化** |
| 5 | AI 权限 | 全渠道**默认「拟稿 + 人工确认」**；仅原生渠道高置信/低风险可自动回复；高风险强制转人工 |
| 6 | 与 spzx 关系 | **独立系统**，通过只读 API/视图对接 spzx 的商品/订单/物流数据 |
| 7 | 结合方式 | 方案一：**Chatwoot 黑盒当壳 + 可替换 AI 大脑**（不做代码级 deep-merge） |
| 8 | 语言选型 | 用户顾虑非 Java 栈的维护/兼容/稳定性 → **AI 大脑改用 Java**；Chatwoot 作为**黑盒 Docker 服务**（不 fork，故无 Ruby 维护负担） |
| 9 | 扩展性 | **壳与大脑都必须可替换**（用户要求未来接其他 AI 项目、慢慢平替 Chatwoot）→ 双 Port + canonical 模型 |
| 10 | 调参试打台 | **AI Brain 自带独立控制台**：单人试打、可调多样性等参数、可存预设并一键提升为线上；**完全沙盒隔离、零外发** |

## 3. 总体架构

```
        买家侧渠道
   网页widget/微信公众号/小程序    抖店(API)      淘宝/拼多多(浏览器)
          │                         │                 │
          │(Ch.原生)      ┌─────────┴─────────────────┴──────┐
          └──────────────►│   Channel Sidecar (Python)       │
                          │   复用现有 Playwright/CDP 生态    │
                          └───────────────┬──────────────────┘
                                          │ canonical 写入
                          ┌───────────────▼──────────────────┐
                          │   Helpdesk Gateway（自建 Java）   │
                          │   统一会话/消息模型（canonical）  │
                          │  ┌ Helpdesk Port ┐  ┌ AI Port ┐  │
                          └──┼────────────────┼──┼─────────┼──┘
                             │                │  │         │
                      ┌──────▼──────┐         │  │  ┌──────▼────────┐
                      │  Chatwoot   │         │  │  │  AI Brain     │
                      │  Adapter    │         │  │  │  (Java)       │
                      └──────┬──────┘         │  │  │ Spring AI/    │
                             │                │  │  │ langchain4j   │
                       [Chatwoot 壳]          │  │  │ RAG·工具·记忆  │
                       收件箱/坐席台/          │  │  └──────┬────────┘
                       工单/帮助中心/报表      │  │         │工具调用(只读)
                                              │  │  ┌──────▼────────┐
                                              │  │  │ spzx Connector│
                                              │  │  │ (Java 只读)   │
                                              │  │  └──────┬────────┘
                                              │  │         │
                                              │  │      [spzx 商品/订单/物流]
```

**四个组件 + 一条核心边界**

| 组件 | 角色 | 技术/来源 | 许可证 |
|---|---|---|---|
| **Chatwoot** | 「人」的一侧：收件箱/坐席工作台/工单/帮助中心/报表 + 原生渠道 | 现成开源，Docker 黑盒，**不 fork** | MIT ✅ |
| **Channel Sidecar** | 电商平台消息 ↔ 平台；每平台一个适配器 | 自建 Python（复用 Playwright/CDP） | 自建 |
| **AI Adapter / AI Port** | 定义大脑的统一接口，隔离具体实现 | 自建 Java 接口 | 自建 |
| **AI Brain** | RAG / 工具调用 / 会话；电商技能 | 自建 Java（Spring AI + langchain4j） | Apache-2.0 ✅ |
| **spzx Connector** | 只读暴露商品/订单/物流/售后给大脑工具 | 自建 Java（spzx 加只读 API） | 自建 |

## 4. 扩展性内核（关键约束，用户明确要求）

**原则：我们拥有自己的「会话中台」和统一数据模型；Chatwoot 与 AI 都只是两端可插拔的实现。**

### 4.1 双 Port

- **Helpdesk Port**：`创建/更新会话`、`写消息`、`分配坐席`、`改状态`、`取会话上下文`。
  今天由 `ChatwootAdapter` 实现（翻译成 Chatwoot API / 消费其 Webhook）。**换壳 = 新写一个 Adapter。**
- **AI Port**：`reply(context, message) -> 回复 | 草稿 | 动作`。
  今天由 `JavaBrainAdapter` 实现。**接其他 AI 项目 = 新写一个 Adapter。**

### 4.2 统一会话模型（canonical，最关键）

- 内部只认自己的一套 `Conversation / Message / Contact / ChannelRef / Tenant` 结构，
  **不泄漏 Chatwoot 或任何 AI 项目的 schema**。
- 上下游全部只说 canonical → 换壳/换脑时改动被锁在一个 Adapter 里，**Channel Sidecar 与 AI 均无感**。
- 与 spzx 对接也用 canonical（商品/订单映射在 Connector 内解决）。

### 4.3 平替能力矩阵

| 想换什么 | 只动 | 不动的 |
|---|---|---|
| 换壳（Chatwoot → 自建/别的） | 新增 Helpdesk Adapter | 渠道、AI、spzx 连接 |
| 换 AI 大脑（→ 其他项目） | 新增 AI Adapter | 壳、渠道、spzx 连接 |
| 加渠道 | 新增 Channel Sidecar | 壳、AI、spzx 连接 |

### 4.4 代价（诚实说明）

多一层 Helpdesk Gateway 和在途同步逻辑，比「直接调 Chatwoot API」复杂一点；
但这层换来的是用户要求的**平替能力**。Phase A 可让 Helpdesk Gateway 与 Chatwoot Adapter **先轻量实现**，
但**接口与模型边界第一天就定死**，避免后续推倒重来。

## 5. 消息全链路（以「抖店买家问『我的货到哪了？』」为例）

```
①平台消息 → ②Sidecar 归一化 → ③写入 Helpdesk Gateway → ④同步 Chatwoot 并触发 AI
   → ⑤AI Brain 推理 → ⑥决策(自动/拟稿/转人工) → ⑦回写 Chatwoot
   → ⑧Sidecar 推回平台 → ⑨买家收到
```

1. **消息进入**：原生渠道直接进 Chatwoot；电商渠道由 Sidecar 轮询/webhook 获取。
2. **归一化**：转成 canonical，**按平台消息ID 去重**（幂等）。
3. **写入 Gateway**：canonical 落库 + 经 Helpdesk Port 同步到 Chatwoot（Contact/Conversation/Message，每平台一个 inbox）。
4. **触发 AI**：Chatwoot `message_created` webhook（来源=买家、非坐席）→ Gateway → AI Port。
5. **AI 推理**（Agent 一轮）：载入上下文 → 意图识别 → RAG 检索 → 按需工具调用 → 生成回复+置信度+来源。
6. **决策**：默认拟稿；原生渠道高置信/低风险可自动发；投诉/退款/超范围 → 转人工（附 AI 摘要）。
7. **回写** → 8. **回推平台**（API 发送；淘宝/拼多多只把文案填进回复框，人工点发送）→ 9. 买家收到。

**横切关注点**：幂等（平台消息ID + 出站标记）、异步排队（AI 推理数秒，不阻塞 webhook）、
转人工与状态（open/pending/resolved + 分配）、可观测留痕（意图/检索命中/工具调用/置信度/是否转人工）。

## 6. 详细设计

### 6.1 Chatwoot 壳

- Docker 部署（含 PostgreSQL + Redis），**只当黑盒，不改 Ruby 代码**。
- 集成方式：**Agent Bot / Webhook / REST API**。升级随官方，维护成本≈0。
- 用一个 Chatwoot **account**（Phase A 单租户）；每渠道一个 **inbox**。

### 6.2 Channel Sidecar（Python）

- **统一适配器接口**：`inbound()` 取平台新消息 → canonical → Gateway；`outbound(msg)` canonical 回复 → 平台。
- 各渠道实现（对齐第 2 节决策）：
  | 渠道 | 方式 | 出站权限 |
  |---|---|---|
  | 网页 widget / 微信公众号 / 小程序 | Chatwoot 原生，无 Sidecar | 高置信自动 / 否则拟稿 |
  | 抖店 | 优先官方 API；拿不到再浏览器 | 拟稿为主 |
  | 淘宝 / 拼多多 | 浏览器自动化（CDP，复用现有 9222 系） | **仅拟稿**，人工点发送 |
- **工程要点**：轮询节奏、登录态维护、**风控冷却自愈**（复用现有 `exit42` 冷却/Wrapper 经验）、健康检查、断点续传。
- **风险隔离**：独立进程，挂了不影响 Chatwoot/Brain；出站全部幂等。

### 6.3 AI Brain（Java）

**6.3.1 知识源（RAG，按店铺/租户隔离）**
- 商品知识：从 spzx 同步 SKU/属性/卖点/尺码/材质。
- 售后政策 + FAQ：人工维护，可从 Chatwoot 帮助中心导入。
- 话术库：历史客服对话（后续从 Chatwoot 会话挖）。
- 平台规则：发货时效/禁词/合规（对齐 `docs/ECOMMERCE_RULES.md`）。

**6.3.2 电商工具（function calling，全部经 spzx Connector 只读）**

| 工具 | 作用 |
|---|---|
| `query_order(买家,店铺)` | 订单状态 |
| `query_logistics(订单号)` | 物流轨迹 |
| `query_product(关键词/SKU)` | 商品信息/库存/尺码 |
| `recommend_product(需求)` | 推荐商品 |
| `escalate_to_human(原因,摘要)` | 转人工（附 AI 摘要） |
| `tag_conversation(...)` | 打标，便于统计 |

写类操作（改价/建售后单）Phase A **不做**，后置且必须人工确认。

**6.3.3 Agent 编排**
- 单主 Agent + 意图路由（Phase A 够用）；结构预留**多 Agent**（售前/售后/物流分工）。
- 工具调用循环设**最大轮数 + 超时兜底**。
- 会话记忆：最近 N 轮 + 超长摘要压缩；买家档案跨会话保留。

**6.3.4 输出契约**
```
{ reply, card?, intent, confidence, sources[], handoff, riskLevel }
```
- `card`：可选结构化卡片（订单/物流/商品），自建渲染。
- 高 `riskLevel` 或低 `confidence` → 强制转人工。

**6.3.5 护栏与提示词边界**
- 不许承诺退款金额/时效、不许编造物流、不许泄露内部信息；不确定→转人工。
- 投诉/退款/纠纷等高风险意图 → 一律转人工。
- 输出过平台合规检查（禁词、平台规则）。

**6.3.6 模型与凭据**
- Provider 可配置（DB 表，照搬 spzx `kw_provider` 的模式），支持 OpenAI 兼容/国内模型；识图需视觉模型。
- 密钥只存 DB/本地配置，**不进仓库**。

**6.3.7 评估**
- 「买家问题黄金集」离线评：RAG 命中率、回复质量、工具正确率。
- 上线后看：CSAT、转人工率、自动解决率。

**技术选型**：Spring AI + langchain4j；向量库用 **pgvector**（独立实例，不占用 Chatwoot 的库）。

### 6.4 spzx Connector（Java，只读）

- 在 spzx 侧**新增只读接口**（或只读视图），绝不复用写路径。
- 暴露：订单、物流、商品、售后 → 映射成 canonical，供 AI 工具调用。
- **鉴权**：服务间 token；调用留痕。
- **商品知识同步**：增量 Job 把 spzx 商品 → Brain 知识库；**订单/物流走实时查询**（不落库同步）。

### 6.5 调参试打台（AI Brain 自带控制台）

**定位**：单人调参试打台。输入/构造一条买家消息，实时调参，观察 AI Brain 的完整推理输出，用于调优多样性、提示词、RAG、模型。**单条试打优先，不做批量回归台。**

**位置**：AI Brain 服务**自带独立控制台**（Spring Boot 内嵌静态 SPA，Vue 3 + Vite + Element Plus），与 spzx 解耦——它调的是 AI Brain 的 canonical 入口，不经 spzx 后端。

**调用链**：
```
控制台 → AI Brain POST /console/preview（沙盒）
  → 复用线上同一套 Agent / Tool / RAG / 护栏 pipeline
  → 仅注入 override 参数 + sandbox 标志
  → 不写 Chatwoot、不写 canonical 生产表、不触发 Sidecar（零外发）
```

**可调参数（6 组）**

1. **生成参数**：temperature / top_p / presence & frequency penalty / seed / max tokens；附「保守 / 均衡 / 创意」预设。
2. **模型与 Provider**：下拉切换；凭据沿用 DB（照搬 spzx `kw_provider` 模式）。
3. **提示词**：可编辑/覆盖 system prompt、人设；面板显示**实际拼装后的完整 prompt**。
4. **RAG 参数**：top-k、相似度阈值、知识源开关；展示命中片段 + 相似度。
5. **模拟上下文**：构造多轮对话、带入订单号/买家身份/店铺。
6. **输出诊断面板**：回复草稿 + intent / confidence / sources[] / 工具调用轨迹 / 决策(自动|拟稿|转人工) / 耗时 / token 用量。

**参数去向**

- 存为**命名预设**（DB 表 `ai_console_preset`：名称 + 参数 JSON + 备注 + 人/时间；Phase B 加 `tenant_id`）。
- **一键提升为线上**：写入线上配置表（`ai_runtime_config`），带二次确认 + **审计**（谁/何时/从哪个预设/改了哪些字段）。**不提供任意直改**，只走预设提升，防手误。
- 线上读取优先级：线上配置表 > 代码默认值。

**沙盒隔离**

- 试打会话存独立沙盒表（`ai_console_session/message`，标 `is_test=1`），**不写 Chatwoot、不写生产会话表、不外发**；可保存/回放/清空。
- 工具调用：默认对真实 spzx **只读**执行（保证真实感）；另有「锁定/模拟」开关，用模拟上下文里的订单号替代，避免误查真实买家。
- 沙盒标志强制生效：出站（Sidecar/Gateway 发送入口）对 sandbox 直接短路，试打路径**运行时也无法外发**。

**API 草案（AI Brain 内）**

- `GET /console/meta` — 可用模型/provider、参数默认、预设列表
- `POST /console/preview` — 试打，返回完整诊断
- `POST /console/preset` / `POST /console/preset/{id}/promote` — 存预设 / 提升线上（审计）
- `GET|DELETE /console/session` — 沙盒会话管理

**安全 / 扩展性**：控制台需鉴权（Phase A 管理员）；只经 AI Port/canonical，不碰 Helpdesk Port → 换壳换脑不受影响。

## 7. 演进路线

- **Phase A（自用单租户）**：本 spec 范围。Chatwoot 黑盒 + Java Brain + Sidecar + spzx 只读。
- **Phase B（多租户 SaaS）**：
  - canonical 加 `tenant_id`；Helpdesk Port 映射到 Chatwoot 的 **account/brand**（天生多账户，适合多租户壳）。
  - Brain：知识库/凭据/配额**按租户隔离**。
  - spzx Connector 泛化成**每租户一个「数据连接器」**（你的 spzx 只是第一个实现）。
  - 补：注册/计费/租户管理。
  - 许可证此时完全干净（无 TGO）。
- **Phase C（AI 员工/运营中枢）**：同一 Port 上再加 Agent（选品/定价/投放/铺货），复用渠道与数据层。

## 8. 风险与错误处理

| 风险 | 对策 |
|---|---|
| 渠道风控/封号 | 拟稿优先、冷却自愈、人工兜底；淘宝/拼多多绝不自动发 |
| AI 幻觉 | RAG 接地 + 置信度阈值 + 高风险类目强制转人工 |
| 资损 | Phase A **零写操作**；回复过合规检查 |
| 平台合规 | 禁词/规则检查、智能客服标识、责任留痕 |
| 单点故障 | 各层独立；AI 挂了消息照样进 Chatwoot，人工接管 |
| 重复回复 | 平台消息ID + 出站幂等标记 |
| 数据隐私 | 租户隔离、密钥只存 DB/本地、日志脱敏 |

## 9. 测试与验收（Phase A）

- **单测**：canonical 映射、幂等、工具入参校验。
- **试打台**：参数 override 合并、预设提升审计、**sandbox 短路外发**（试打路径无法外发）。
- **集成**：Mock 渠道 + 真实 Chatwoot 跑通一条消息端到端。
- **AI 评估**：买家问题黄金集（RAG 命中/回复质量/工具正确率）。
- **验收标准**：①原生渠道 AI 拟稿/自动回复可用；②至少一个真实电商渠道（抖店）闭环；③查订单/物流准确；④转人工可用；⑤无重复回复、无任何写操作；⑥调参试打台可见完整诊断、改多样性可见回复变化、预设可提升且线上生效、试打不产生任何真实外发。

## 10. 许可证汇总

| 项目 | 许可证 | 用途 | 结论 |
|---|---|---|---|
| Chatwoot | MIT（`enterprise/` 除外） | 壳（黑盒、不 fork） | ✅ 干净 |
| Spring AI / langchain4j / ragent | Apache-2.0 | AI 大脑 | ✅ 干净 |
| ruoyi-ai | MIT | AI 大脑备选 | ✅ 干净 |
| Bytedesk | AGPL-3.0 | 壳备选（未采用） | ⚠ 仅备用 |
| TGO | 修改版 Apache-2.0 | **已弃用** | 多租户授权风险清零 |

## 11. 开源项目调研结论

**Chatwoot**：成熟客服工作台（收件箱/工单/帮助中心/报表/多渠道/CSAT），强在「人」的一侧，AI（Captain）是后加插件。
**TGO**：AI 原生客服（Agent 编排/RAG/MCP/工作流/电商富卡片），强在「AI」的一侧，但年轻（627★）+ SaaS 需授权。

**结合判断**：两者是客服平台互补的两半，可结合；但**不做代码级 deep-merge**（三套栈 + 许可证不兼容）。
最终取「Chatwoot 黑盒当壳 + 自建 Java 大脑」，既拿 Chatwoot 的成熟度与 MIT 干净，又让大脑与 spzx 同栈、许可证干净。

**Java 生态调研**（用户顾虑非 Java 栈）：AI 大脑有 Spring AI / langchain4j / ruoyi-ai / ragent 等成熟且许可干净的项目；
「客服壳」的 Java 对位较薄弱，唯一像样的是 Bytedesk（AGPL）。故壳仍用 Chatwoot（黑盒，无维护负担），大脑改 Java。

## 12. 待决 / 开放问题

1. **抖店飞鸽官方 API 的开通资质**：需登录抖音电商开放平台实地核实接口名与条件（Phase A 第一周做渠道可行性 spike）。
2. **拼多多是否有客服消息 API**：存疑，需核实；不确定则走浏览器拟稿。
3. **AI Brain 起步形态**：Spring AI 自建薄服务 vs 以 ruoyi-ai 为底座，待实现前一并定。
4. **部署环境**：Phase A 先单机 Docker Compose，生产服务器选型待定。
5. **Chatwoot 中文/微信渠道适配度**：需实测微信公众号/小程序接入的实际工作量。

## 13. 非目标（本次不做）

- Phase B（多租户、计费、租户隔离）与 Phase C（运营 Agent）——仅在本文记录路线。
- 任何写类电商操作（改价、退款、建售后单）。
- 淘宝/拼多多的自动发送（仅拟稿）。
- 对 Chatwoot 或任何 AI 项目源码的修改（一律黑盒集成）。
