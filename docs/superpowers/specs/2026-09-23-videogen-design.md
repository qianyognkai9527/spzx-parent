# 智能短视频生成（videogen）设计文档

日期：2026-09-23　状态：已评审通过（待实施计划）
决策记录：视频模型选 **火山方舟 Seedance**（图生视频，首帧 base64 提交）；"宝贝Id" = 本地 `platform_product.id`。

## 1. 目标

运营后台输入一个商品 id，系统自动：
1. 用现有 LLM 通道分析商品（标题+图集）产出**短视频分镜提示词**（可人工编辑）；
2. 用提示词 + 商品首图调 Seedance **图生视频**；
3. 成片转存 MinIO，前端预览与**下载 mp4**。

非目标（明确不做）：批量生成、口播 TTS/字幕、自动发布到抖音、文生视频模式、首帧图自由选择（默认取 `product_media` 主图第一张）。

## 2. 架构与复用

```
前端「短视频生成」页（新模块 views/videogen/）
   │ ①POST /admin/videogen/prompt        ②POST /admin/videogen/task
   ▼                                     ▼
VideoPromptService                    VideoGenTaskService（线程池 2 / 队列 20）
   │ 复用 KwAiClient.vision               │ 1. 读首图→base64→提交 Ark 任务 API
   │ (识品同款多模态通道)                  │ 2. 轮询 3~10s，超时 15min
   ▼                                     │ 3. 下载成片（Ark 公网 URL）
 分镜脚本 + 最终 prompt JSON              │ 4. putObject 转存 MinIO → SUCCEEDED
                                         ▼
                                    前端轮询任务列表 → <video> 预览 + 下载
```

复用清单：`KwAiClient`（prompt 生成）、`kw_provider` 表（AK 管理，扩 video 能力）、`kw_select_task` 的任务生命周期模式、MinIO `FileServiceImpl`（扩字节上传）、前端 kw/task 页轮询模式、`PageQueryUtil` 分页。

## 3. 数据模型

### 3.1 新表 `video_gen_task`

```sql
CREATE TABLE video_gen_task (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  product_id BIGINT UNSIGNED NOT NULL COMMENT 'platform_product.id',
  prompt VARCHAR(2000) NOT NULL COMMENT '最终提交的视频提示词(可编辑)',
  prompt_source TINYINT NOT NULL DEFAULT 1 COMMENT '1=AI生成 2=人工编辑',
  model VARCHAR(64) NOT NULL COMMENT 'Ark 模型编号,如 doubao-seedance-1-0-pro-250528',
  duration TINYINT NOT NULL DEFAULT 5 COMMENT '秒: 5|10',
  ratio VARCHAR(8) NOT NULL DEFAULT '9:16' COMMENT '9:16|1:1|16:9',
  status TINYINT NOT NULL DEFAULT 0 COMMENT '0排队 1已提交 2生成中 3成功 4失败',
  remote_task_id VARCHAR(64) DEFAULT NULL COMMENT 'Ark 任务id',
  object_key VARCHAR(256) DEFAULT NULL COMMENT '成片 MinIO 键 videogen/yyyyMMdd/uuid.mp4',
  error_msg VARCHAR(500) DEFAULT NULL,
  finish_time DATETIME DEFAULT NULL,
  create_by BIGINT UNSIGNED, create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  is_deleted TINYINT NOT NULL DEFAULT 0,
  KEY idx_product (product_id), KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI短视频生成任务';
```

### 3.2 provider 扩展

`ALTER TABLE kw_provider ADD COLUMN video_model VARCHAR(64) DEFAULT NULL COMMENT '视频生成模型编号';`
`KwProviderService.modelFor("video")` → `video_model`；创建任务时 `requireActive(provider, "video")` 校验。provider 选择沿用 `kw_config` 模式（新增 KEY_VIDEO）。

## 4. Ark Seedance 接口约定（适配层）

- 提交：`POST {base_url}/contents/generations/tasks`，`Authorization: Bearer {api_key}`，body：`{model, content:[{type:"text", text:prompt},{type:"image_url", image_url:{url:"data:image/jpeg;base64,..."}}], generate_audio:false}`（duration/ratio 走模型参数，按 Ark 文档字段为准，实现时核对）。
- 查询：`GET {base_url}/contents/generations/tasks/{task_id}` → `status: queued|running|succeeded|failed`，成功取 `content.video_url`（有效期约 24h，故必须转存 MinIO）。
- 实现为 `ArkVideoClient`（hutool HttpRequest，风格同 KwAiClient）：`submit()/poll()` 两方法 + 错误信息映射（额度不足/内容审核不通过/参数错误 → 中文 errorMsg）。
- 审核失败与 4xx 不重试；5xx/超时轮询容忍 3 次连续失败。

## 5. 后端接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/admin/videogen/prompt` | `{productId}` → 同步返回 `{storyboard:[…], prompt:"…"}`（复用识品通道，失败 204） |
| POST | `/admin/videogen/task` | `{productId, prompt, duration, ratio}` → 建任务入队，返回 id |
| GET | `/admin/videogen/task/list/{p}/{s}` | 分页（ProductQueryUtil），可按 status/productId 过滤 |
| GET | `/admin/videogen/task/{id}` | 详情（前端轮询单条状态） |
| POST | `/admin/videogen/task/{id}/retry` | 仅 FAIL 可重试：重置为排队、清 error_msg，重新入队 |
| DELETE | `/admin/videogen/task/{id}` | 软删（MinIO 对象保留，后续做清理任务） |
| GET | `/admin/videogen/task/{id}/download` | 302 到 MinIO URL（文件名 `code_任务id.mp4`） |

校验：prompt 非空且 ≤2000；productId 必须存在于 platform_product；duration ∈ {5,10}；ratio 白名单。队列满时任务直接落 FAIL + "队列已满"（不留排队孤儿，吸取 kw 教训）。

## 6. 提示词生成（VideoPromptService）

输入：商品标题、价格、类目/交易分类、最多 4 张主图（base64/URL 同识品）。
要求 LLM 输出 JSON：`{"storyboard":[{"shot":1,"desc":"…","camera":"推近","sec":2}…], "prompt":"一段可直接提交 Seedance 的中文画面描述…", "cover_hint":"建议首帧图序号"}`。
prompt 组装规则（写死在模板里）：主体=商品实物、9:16 竖屏、卖点场景化（人群+使用场景+情绪）、规避文字/水印描述、结尾引导动作。前端展示分镜列表 + 可编辑的最终 prompt。

## 7. 前端页面（views/videogen/index.vue + 新路由模块）

- 上半区：商品选择弹窗（复用 kw product 列表接口，主图/标题/价格）→「AI 生成提示词」→ 分镜卡片展示 + prompt textarea 可编辑 → 时长/比例选择 →「开始生成」。
- 下半区：任务列表（ProTable）：商品、状态徽标（排队/生成中/成功/失败）、耗时、操作（预览/下载/重试/删除）；存在进行中任务时 5s 轮询（页面 activate/deactivate 启停，吸取 keep-alive 教训）。
- 预览：el-dialog + `<video controls :src="minioUrl">`。
- 菜单：`videogen_init.sql` 建表 + 幂等 sys_menu/sys_role_menu 注册（挂"运营"下，component=路由 name `videogen`）。

## 8. 错误处理与安全

- 全接口走登录鉴权（不加白名单）；无字符串拼 SQL；provider apiKey 仅存 DB，不打印到日志（KwAiClient 现有语义保持）。
- LLM 返回非 JSON：剥 ``` 围栏 + 截取首尾花括号重试解析，失败报 204。
- 成片下载链接为 MinIO 匿名读路径：对象键含 UUID 不可枚举；bucket 若公共读，视频属营销素材可接受（记录在案）。
- 与既有一致：@Transactional 不包住外部调用；异步执行器内 DB 写均为短事务。

## 9. 测试与验收

- 无正式测试套件环境下，验收以真实链路：① 对样例商品（platform_product 有图数据）生成提示词成功且可编辑；② 提交后任务状态推进到 SUCCEEDED，MinIO 出现 mp4；③ 前端预览/下载/重试/删除全路径；④ 错误路径：不配 video_model 时报错文案、队列满、审核失败。
- 编译验证：`mvn compile -pl spzx-manager -am`；前端 `npm run build`。

## 10. 实施增量与工作量（≈6 人日）

| 增量 | 内容 | 人日 |
|---|---|---|
| I1 提示词生成 | prompt 接口 + VideoPromptService + 前端上半区（可独立验收） | 1.5 |
| I2 生成链路 | 表+provider扩展+ArkVideoClient+任务执行器+MinIO转存+接口全套 | 2.5 |
| I3 前端与联调 | 任务列表页 + 预览下载 + 真实 Key 端到端（含错误路径） | 2 |

扩展方向（后续单独立项）：批量生成与抽卡、首帧图人工选择、口播文案+TTS 合成、数字人、发布链路对接、视频封面截取。
