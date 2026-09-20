# 大模型 Provider 配置页面化（kw 引擎配置）设计文档

日期：2026-09-20 ｜ 状态：待用户审阅
前置：AI 选词推广助手（2026-09-18 设计、09-19 交付，见 `2026-09-18-ai-keyword-select-design.md`）

## 1. 背景与目标

现状：provider 的「选择」已存 DB（`kw_config` 表，切换即时生效），但 provider 的「定义」（base-url、api-key、模型名、max-tokens、extra-body）仍写死在 `application-local.yml`（gitignored）。后果：换引擎不用重启，但**改 key、改模型、新增 provider 必须改 yml + 重启 8501**。

目标：provider 定义全部搬进 DB，后台新增「AI引擎配置」页面——新增/编辑/停用 provider、填 key、改模型、测连通、切换文本/视觉主用引擎，全部页面操作即时生效，不再碰 yml、不再重启。

## 2. 范围

**本期做：**
- 新表 `kw_provider` 存 provider 定义；首次启动从 yml 自动播种（表空才播，之后 yml 的 `kw.providers` 节作废不再读取）
- Provider CRUD + 启用/停用 + 连通测试 + key 脱敏
- 主用引擎切换扩展到文本+视觉两个维度（现状 PUT 只开放了文本，前端无任何入口）
- `KwAiClient` 改为运行时直读 DB（每次调用现读，不缓存——本地 MySQL 单查 ~1ms，对比 LLM 秒级调用可忽略，零缓存失效问题）
- 前端「AI引擎配置」页面（菜单挂「运营管理」下，AI选词三页面旁）
- `image_model` 预留列（子项目 B 生图用，本期只留列不实现生图）

**本期不做：**
- 子项目 B 生图功能本身（火山方舟 Doubao-Seedream）
- 创意工具 `CreativeToolServiceImpl` 的智谱 zhipu 配置迁移（孤儿服务，等它接 Controller 时再说）
- 视频第 4/5 步（投放数据 7 天复核轮）
- 权限分级（页面沿用现有后台登录鉴权，单管理员场景不做细粒度权限）

## 3. 总体设计

```
「AI引擎配置」页面 ──CRUD/切换/测试──> spzx-manager ──> MySQL
                                                        │
AI选词任务(KwTaskService) ──providerName──> KwAiClient ──┘ 每次调用现读
                                              │
                                              ▼
                                   provider 定义 + 当前主用选择( kw_config )
```

- `kw_config` 职责不变：只存「当前主用引擎」两个键 `text_provider` / `vision_provider`
- `kw_provider` 新职责：存「provider 定义」，name 即唯一标识
- 不做内存缓存；不做配置刷新机制（无重启是靠"每次现读"实现的，最简单且不会失效）

## 4. 数据库（db_spzx，DDL 追加进 `spzx-manager/src/main/resources/sql/kw_init.sql` 并手动执行）

```sql
CREATE TABLE kw_provider (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL COMMENT '唯一标识，创建后不可改（任务快照按 name 引用）',
  base_url VARCHAR(200) NOT NULL,
  api_key VARCHAR(500) NOT NULL DEFAULT '' COMMENT '明文本地存储，与今日 yml 等级一致，不入 git',
  vision_model VARCHAR(100) DEFAULT '',
  text_model VARCHAR(100) DEFAULT '',
  image_model VARCHAR(100) DEFAULT '' COMMENT '预留：子项目B生图模型，本期不读',
  max_tokens INT DEFAULT 4096,
  extra_body VARCHAR(1000) COMMENT 'JSON对象字符串，如 {"thinking":{"type":"disabled"}}',
  status TINYINT DEFAULT 1 COMMENT '1启用 0停用',
  remark VARCHAR(255),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_name (name)
);

-- 菜单：运营管理(parent_id=38)下，AI选词三页面(65-67)之后
INSERT INTO sys_menu(id, parent_id, title, component, sort_value, status, is_deleted)
VALUES (68, 38, 'AI引擎配置', 'kwConfig', 63, 1, 0);
```

**播种（自动，代码实现）**：启动时 `kw_provider` 为空且 yml `kw.providers` 非空 → 按 yml 现值插入 3 条（tokens-store / deepseek / volcengine-ark），status=1，extra_body 序列化为 JSON 字符串，打日志「已从 yml 播种 N 个 provider」。表不存在时仅 log.warn 跳过，不阻塞启动。播种后 yml 该节不再被读取（KwProperties.providers 仅剩播种用途）。

`kw_config` 现有 2 行值（tokens-store）与播种 name 天然对齐，无需迁移。

## 5. 后端（spzx-manager）

### 5.1 新增 `KwProviderService`（service/kw，运行时配置源）

- `ProviderDef get(String name)`：按 name 查单条（含 extra_body 反序列化为 Map）
- `ProviderDef requireActive(String name, String kind)`：校验存在 + status=1 + 有 key + kind 对应模型已配，不满足抛 RuntimeException（沿用 KwAiClient 现有报错语义，如「AI provider 未配置/已停用: xxx」「未配置 vision 模型」）
- `List<ProviderDef> listAll()`
- 每次现读 DB，无缓存

### 5.2 改造 `KwAiClient`

- `call()` 里 `props.getProviders().get(providerName)` → `kwProviderService.requireActive(providerName, kind)`
- 其余全部不动：2 次重试、max_tokens、extraBody 逐键合并进请求体、POST `base_url + /chat/completions`、timeout 仍取 `props.getTimeoutMs()`、stripFence
- 对外方法签名不变（调用方 `KwTaskService` 零改动；任务创建时的 textProvider 快照语义不变）

### 5.3 新增 `KwProviderController`（`/admin/kw/provider`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/list` | 全量列表；**apiKey 不回传**，只回 `hasKey` + `keyTail`(尾4位) |
| POST | `` | 新增；name 唯一校验；extraBody 必须合法 JSON 对象（否则 204 报错）；status 默认 1 |
| PUT | `` | 更新；**name 不可改**；apiKey 为空/缺失 = 保留原值；extraBody 同样校验 |
| PUT | `/status/{id}/{status}` | 启用/停用；停用前校验非当前主用（text/vision 任一命中则拒绝，提示先切换） |
| DELETE | `/{id}` | 仅允许删除非当前主用的 provider（在途任务快照按 name 引用，删除后其调用会报「provider 不存在」，属可接受语义，前端二次确认） |
| POST | `/test/{id}` | 连通测试：优先 textModel、无则 visionModel，都无 → 报错；发 `max_tokens=16` 的 "ping" 单轮消息；返回 `{ok, costMs, error}`，不落库、不影响重试计数 |

### 5.4 扩展 `KwConfigController`

- GET `/admin/kw/config`：返回 textProvider / visionProvider / providers（name、hasKey、keyTail、两模型、status）
- PUT `SetDto` 扩展为 `{textProvider?, visionProvider?}`：传了才改；逐个校验「存在 + 启用 + 有 key」，不满足 204 返回明确错误

### 5.5 `KwProperties` 去留

- `providers` 字段保留（仅作播种数据源），类上注释标明「providers 仅用于首次播种，运行时配置在 kw_provider 表」
- `timeoutMs/topN/batchSize/minPopularity/imageCount/weights` 继续走 yml，本期不动

## 6. 前端（spzx-admin）

- `src/api/kw.js` 追加（沿用 request util + `api_name='/admin/kw'`）：GetKwProviderList / SaveKwProvider(POST/PUT) / UpdateKwProviderStatus / DeleteKwProvider / TestKwProvider / GetKwEngineConfig / SwitchKwEngine
- `src/router/modules/kw.js` 加路由 `/kwConfig`（name: kwConfig）
- `src/views/kw/config/index.vue`：
  - **顶部两张引擎卡片**：当前文本引擎 / 当前视觉引擎，el-select 列出启用中的 provider，选中即调 SwitchKwEngine，成功 ElMessage 提示「即时生效，无需重启」
  - **provider 表格**：名称 / base_url / 文本模型 / 视觉模型 / max_tokens / API Key(脱敏尾4位) / 状态 tag / 备注 / 操作（编辑、测试、停用|启用、删除）
  - **新增/编辑 dialog**：name（编辑时 disabled，注明「创建后不可改，任务按 name 引用」）、base_url、api_key（编辑时 placeholder「留空则不修改」）、vision_model / text_model / image_model(标注预留)、max_tokens、extra_body（textarea，前端 JSON.parse 校验 + 格式示例 placeholder）、remark
  - 测试按钮带 loading，结果显示 ok+耗时 或 错误信息
- 页面顶部加一行说明文字：「模型名与 provider 绑定；换 provider 后建议先跑一个小任务验证（thinking 类参数属模型家族，可能需调整 extra_body）」——把 AGENTS.md 里那个老坑显式提示给操作者

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| 换 provider 后 thinking 参数不适用（已知坑：tokens.store deepseek 需 thinking disabled） | extra_body 每 provider 独立存储可分别调整 + 页面提示语 + /test 快速验证 |
| 播种只发生一次，之后改 yml 无效，未来容易困惑 | KwProperties 注释 + 本 spec + AGENTS.md 更新说明 |
| 删除 provider 导致在途任务调用失败 | 删除仅限非主用 + 前端二次确认 + 报错信息明确（「provider 不存在或已停用」） |
| key 从 gitignored yml 挪到 DB，担心泄漏面扩大 | 同机 MySQL 明文，与现状等级一致；接口层脱敏不回传完整 key；yml 播种后应把 key 从 yml 中清掉（验收项） |

## 8. 验收标准

1. 重启后端一次：`kw_provider` 自动播种 3 条，页面可见、key 脱敏显示
2. 页面修改 tokens-store 的 textModel → 不重启 → 新建选词任务，日志显示新模型名
3. 页面新增一个 provider（填 key）→ 测试连通 ok → 切换文本引擎到它 → 跑选词任务成功
4. 视觉引擎切换生效：切到另一 provider 后识品任务按新 provider 的 visionModel 调用
5. 停用当前主用 provider → 被拒绝并提示先切换；切换到无 key 的 provider → 被拒绝
6. extra_body 填非法 JSON → 前端拦截保存
7. `mvn compile -pl spzx-manager -am` 通过；前端 `npm run build` 通过
8. 播种验收通过后，`application-local.yml` 的 `kw.providers` 三个 api-key 清空（凭据唯一来源 = DB）
