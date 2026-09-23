# AI 选词推广助手 设计文档（子项目 A）

日期：2026-09-18 ｜ 状态：待用户审阅

## 1. 背景与目标

来源：内训课视频《AI自动化选词推广》工作流的前 3 步（建词表 → AI 识品 → AI 匹配选词），集成进现有运营管理后台（spzx-parent + spzx-admin）。

目标：运营在后台选择一个商品 → 上传生意参谋导出的词表 → AI 自动识品并匹配出可选关键词 + 优化标题建议 → 导出用于直通车推广。

## 2. 范围

**本期做：**
- 词表 Excel 上传、解析、去重、4 维加权打分
- AI 识品（视觉模型看商品图 + 标题 → 产品拆分描述，替代视频里人工写 TXT 小传）
- AI 选词匹配（文本模型，输出匹配度+理由）
- 标题优化建议（3 个候选 + 理由）
- 结果展示、勾选、导出 Excel

**本期不做（后续子项目/二期）：**
- CDP 自动拓词脚本（生意参谋关联词循环拓展；当前走路线 b：Top300+人工拓展，几千词规模）
- 投放数据 7 天复核轮（视频第 4/5 步）
- AI 主图生成（子项目 B，模型选火山方舟 Doubao-Seedream-5.0-pro）

## 3. 总体流程（后台页面「AI选词」）

1. **选商品**：`platform_product` 分页列表，支持标题搜索/平台筛选（淘宝/抖音），展示标题、前 5 张图、价格
2. **传词表**：上传生意参谋导出 Excel（可多文件合并），解析列名映射 → 去重 → 打分入库为「词表批次」
3. **创建任务**（异步，前端 3s 轮询）：
   - ② 识品：取商品图前 5 张（`product_media`，按排序取）+ 标题 + 用户可选补充说明 → 视觉模型（默认 qwen3.8-max，provider/model 可配）→ 产品描述 JSON
   - ③ 选词：产品描述 JSON + 词表（规则粗筛后按得分 Top 2000，500 词/批）→ 文本模型（默认 deepseek-v4-flash，provider/model 可配）→ 每词匹配度+理由
   - 标题优化：高分匹配词 + 淘宝标题规则（≤30 汉字/60 字符）→ 3 个候选标题+理由
4. **结果页**：词表格（AI 匹配度/词表得分/理由，可勾选、导出 xlsx）+ 标题建议卡片

任务状态机：`0待跑 → 1识品中 → 2选词中 → 3完成 / 4失败`（识品结果落库，失败重试不重跑②）。

## 4. 数据库（db_spzx 新增 6 表，`kw_` 前缀，不复用现有空表 keyword_plan_*）

```sql
CREATE TABLE kw_wordbank_batch (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL COMMENT '批次名，如 睡衣女冬-0918',
  platform_type TINYINT DEFAULT 1 COMMENT '1淘宝 2抖音',
  file_names VARCHAR(500) COMMENT '来源文件名，逗号分隔',
  word_count INT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  remark VARCHAR(255)
);

CREATE TABLE kw_wordbank_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id BIGINT NOT NULL,
  keyword VARCHAR(120) NOT NULL,
  search_popularity INT COMMENT '搜索人气',
  click_rate DECIMAL(8,4) COMMENT '点击率',
  conv_rate DECIMAL(8,4) COMMENT '点击转化率',
  buyer_count INT COMMENT '买家数',
  score DECIMAL(8,4) COMMENT '加权总分',
  UNIQUE KEY uk_batch_kw (batch_id, keyword),
  KEY idx_batch_score (batch_id, score)
);

CREATE TABLE kw_product_analysis (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  platform_type TINYINT,
  title VARCHAR(100),
  images JSON COMMENT '送AI的图片url列表',
  ai_desc JSON COMMENT '产品拆分描述JSON',
  note VARCHAR(500) COMMENT '用户补充说明(材质/人群等)',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE kw_select_task (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  batch_id BIGINT NOT NULL,
  analysis_id BIGINT COMMENT '识品结果id',
  status TINYINT DEFAULT 0 COMMENT '0待跑 1识品中 2选词中 3完成 4失败',
  error_msg VARCHAR(500),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  finish_time DATETIME
);

CREATE TABLE kw_task_word (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  keyword VARCHAR(120) NOT NULL,
  match_score INT COMMENT 'AI匹配度0-100',
  bank_score DECIMAL(8,4) COMMENT '词表得分',
  reason VARCHAR(200) COMMENT 'AI理由',
  picked TINYINT DEFAULT 0 COMMENT '用户勾选',
  KEY idx_task (task_id)
);

CREATE TABLE kw_title_suggestion (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  title VARCHAR(60) NOT NULL,
  reason VARCHAR(300)
);
```

## 5. 评分规则

四维归一化后加权（默认，常量可调）：

```
score = 0.30×norm(搜索人气) + 0.25×norm(点击率) + 0.25×norm(点击转化率) + 0.20×norm(1/(买家数+1))
```

- 买家数少 = 写这词的卖家少 = 竞争红利，得分高（视频核心逻辑）
- 硬过滤：搜索人气 < 60 剔除（视频：「至少不能是五六十」）
- norm 为批次内 min-max 归一化

## 6. AI 设计

### Provider 抽象（多供应商配置化，核心）

**使用场景（用户核心诉求）**：平时走 tokens.store 中转站省事；下班/周末空闲时段切自己 DeepSeek 官方 key 吃峰谷价，跑批量选词省钱。切换是**日常运营动作**，不是一次性部署配置。

所有 chat 类 provider 统一走 **OpenAI 兼容 `/chat/completions` 协议**，一个 `KwAiClient` 通吃：
- `kw.providers.<name>` 内**绑定该家的 base-url + api-key + 模型名**（各家模型 ID 不同，如 tokens.store 的 `deepseek-v4-flash` vs 官方的 `deepseek-v4.1-flash`，模型名跟 provider 走才不会切错）
- 运行时**当前用哪个 provider 存 DB**（前端开关切换，即时生效，不重启后端）；yml 只存凭据
- 识品永远走有视觉的 provider（DeepSeek 官方无视觉模型，vision 不参与切换）；可省的钱在选词+标题（成本大头）
- 已实测（2026-09-18，tokens.store key）：`qwen3.8-max` 视觉识别准确、纯文本 1.5s；`qwen3.8-flash` 视觉可用；`glm-5.3-flash` 文本可用（reasoning 模型，max_tokens 需 ≥2000）
- 项目内已有同类先例 `CreativeToolServiceImpl`（hutool HttpRequest 调 OpenAI 兼容接口 + `@Value` 配置），KwAiClient 沿用该模式升级为多 provider；**CreativeToolService 本身保持不动**

### ② 识品（默认 qwen3.8-max，原生多模态）
输入：≤5 张商品图 + 标题 + 补充说明（可空）。
输出强制 JSON：
```json
{
  "category": "叶子类目",
  "material": "材质",
  "fit": "版型",
  "audience": {"gender": "", "age": "", "scene": ""},
  "style": "风格",
  "season": "季节",
  "selling_points": [],
  "exclude_dims": [{"dim": "年龄段", "avoid_keywords": ["儿童", "童"]}],
  "seed_keywords": []
}
```
失败处理：JSON 解析失败重试 1 次，仍失败任务置失败。

### ③ 选词（默认 deepseek-v4-flash，非思考模式；要求 JSON 输出）
- 粗筛：词含 exclude_dims 的 avoid_keywords → 直接过滤；剩余按 score 降序取 Top 2000（配置）
- 分批 500 词/批（词+四维数据），要求只输出 JSON 数组 `[{"keyword","match_score","reason"}]`，解析失败该批重试 1 次
- 结果合并入库，页面按 match_score 降序
- 提质量可换 `deepseek-v4-pro`（改一个配置项）

### 标题优化（默认 deepseek-v4-flash）
输入：原标题 + match_score Top 30 词。约束：≤30 汉字、含高分词、不堆砌违禁、空格分词。输出 3 个候选+理由。

### 成本估算
单任务：识品 1 次视觉模型（约几分钱）+ 选词 4 批文本模型（约几分钱）≈ 每商品 < 0.2 元。

## 7. 接口设计（spzx-manager，/admin/kw 前缀，走现有鉴权）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /admin/kw/product/list | 商品分页（keyword/platform_type） |
| GET | /admin/kw/product/{id}/images | 商品前 5 张图 |
| POST | /admin/kw/wordbank/upload | multipart：files[] + name + platformType |
| GET | /admin/kw/wordbank/batch/list | 批次列表 |
| GET | /admin/kw/wordbank/batch/{id}/items | 批次词条分页 |
| POST | /admin/kw/task/create | {productId, batchId, note} → taskId |
| GET | /admin/kw/task/list | 任务列表 |
| GET | /admin/kw/task/{id} | 状态 + 结果（词/标题） |
| POST | /admin/kw/task/{id}/retry | 失败重试 |
| POST | /admin/kw/task/{id}/pick | 勾选词 |
| GET | /admin/kw/task/{id}/export | 导出 xlsx |
| GET | /admin/kw/config | 当前引擎（text/vision 各走哪个 provider + 可选项列表） |
| PUT | /admin/kw/config | 切换引擎 {textProvider}（存 DB 即时生效；进行中任务沿用启动时引擎） |

## 8. 前端（spzx-admin）

新增菜单「AI选词」（sys_menu 配置），`src/views/kw/` 下三个页面：
- `product/index.vue`：商品选择（表格+搜索）
- `wordbank/index.vue`：词表批次（上传对话框+列表+词条查看）
- `task/index.vue`：任务列表+详情（状态轮询、词表格勾选、标题卡片、导出按钮；**页顶「AI引擎」开关**：tokens.store ⇄ DeepSeek官方，下班/周末切官方峰谷价跑批量）
组件全部 Element Plus 常规件，Pinia 不需要新 store。

## 9. 配置（application-local.yml 存凭据不进 git，确认 .gitignore 覆盖；当前 provider 存 DB）

```yaml
kw:
  # 各家凭据+模型名绑定（模型名跟 provider 走，切换不错配）
  providers:
    # 默认：tokens.store 中转站（OpenAI 兼容，用户已购 token）
    tokens-store:
      base-url: https://tokens.store/v1
      api-key: ek-xxx
      vision-model: qwen3.8-max      # 备选: qwen3.8-flash（省）
      text-model: deepseek-v4-flash  # 备选: glm-5.3-flash、deepseek-v4-pro
    # DeepSeek 官方（峰谷价，下班/周末切过来跑批量选词省钱）
    deepseek:
      base-url: https://api.deepseek.com/v1
      api-key: ""
      text-model: deepseek-v4.1-flash  # 可换 deepseek-v4 / deepseek-v4-pro；以官方实际模型 ID 为准
    # 预留：火山方舟（子项目 B 主图生成 Doubao-Seedream-5.0-pro，走 images 接口，单独实现 ArkImageClient）
    volcengine-ark:
      base-url: https://ark.cn-beijing.volces.com/api/v3
      api-key: ""
  # ↓ 非凭据参数固定走 yml
  top-n: 2000
  batch-size: 500
  min-popularity: 60
  image-count: 5
  weights: {popularity: 0.30, clickRate: 0.25, convRate: 0.25, buyer: 0.20}
```

绑定方式：`@ConfigurationProperties(prefix = "kw")` 绑定凭据/模型名；**当前 vision/text 用哪个 provider 存 DB**（实现时确认复用 sys_config 还是新建 `kw_config(config_key, config_value)` 单表），前端开关读写，即时生效不重启。识品默认固定 tokens-store（除非其挂掉），选词/标题由用户随时切换。

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| 生意参谋导出 Excel 真实列名/格式未知 | 解析器做列名映射表；用户导出首个真实文件后校准（验收前置条件） |
| AI 返回非 JSON | prompt 强约束 + 重试 1 次 + 失败可重试 |
| 词表超预期大 | Top2000 截断 + 分批 |
| product_media 实际字段结构未核对（图片URL/排序/视频图区分） | 实现前先 DESCRIBE 核对，取图逻辑按真实字段调整 |
| AI 慢（识品 10-30s，选词 1-3min） | 异步任务 + 前端轮询，不同步阻塞 |
| tokens.store 中转站偶发慢/挂（已实测到一次视觉请求 120s 超时，重试即恢复） | 调用超时 180s + 重试；provider/model 全配置化，中转不稳可随时切官方 |
| 切到 DeepSeek 官方但 key 为空/欠费 | 切换接口校验 provider 凭据已配置（key 非空），否则拒绝切换；任务失败列表显示明确错误 |

## 11. 验收标准

1. 上传真实生意参谋 Excel → 打分列表正确（去重、过滤、排序可人工核对）
2. 选一个真实商品跑完整任务 → 产出匹配词（理由合理、无排除维度词如"儿童"混入）+ 3 个合规标题
3. 失败重试、导出 xlsx 可用
4. 用户人工评估选词质量满意
