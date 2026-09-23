# AI 选词推广助手（子项目 A）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 spzx 运营后台落地「AI选词」：词表上传打分 → AI 识品 → AI 选词匹配 → 标题优化 → 勾选导出，AI 引擎多 provider 配置化（tokens.store 默认 / DeepSeek 官方峰谷省钱可切换）。

**Architecture:** 后端 Spring Boot 3.3.5 单体（spzx-manager）新增 `kw` 服务族：OpenAI 兼容 `KwAiClient` 统一调多 provider（凭据在 application-local.yml，当前用哪家存 DB `kw_config` 表即时切换）；`kw_select_task` 异步状态机（0待跑→1识品中→2选词中→3完成/4失败）；前端 spzx-admin 新增 `views/kw/` 三页面挂动态菜单。

**Tech Stack:** Java 21 + MyBatis-Plus 3.5.9 + hutool HTTP/JSON + EasyExcel（词表解析/导出）+ Vue 3 + Element Plus + ProTable。

**设计文档（spec）:** `docs/superpowers/specs/2026-09-18-ai-keyword-select-design.md`

## Global Constraints

- 后端**无测试套件且 AGENTS.md 禁 `mvn test`**（会拉 Spring 上下文）。每个任务的验证 = `mvn compile` 通过 + curl 实测接口 + mysql 查数。不要写 @SpringBootTest。
- mvn 用 IntelliJ 内置 Maven：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`；改动涉及实体时先 `mvn install -pl spzx-model -DskipTests -q` 再 compile manager。
- 预先存在的编译错误（与本次无关，勿动）：`AbstractWechatPayStrategy:49`、`PaypalOrderStrategy:45`、`StripeCardStrategy:46`。验证编译时只看自己文件的报错。
- MySQL：`/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx`。若 3306 未起需先启动（AGENTS.md 有 osascript 命令）。
- API 风格：`@RestController` + `@RequestMapping("/admin/kw/...")`，返回 `com.joker.spzx.model.vo.common.Result`，用 `Result.build(data)`；鉴权由全局拦截器按 /admin 前缀处理，控制器不写鉴权代码。
- Mapper 一律 `@Mapper` 注解（项目无 @MapperScan）。
- 实体放 `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/`，风格照 `entity/oper/MallProduct.java`：`@TableName` + `@TableId(value="id", type=IdType.AUTO)` + `@TableField` + lombok `@Data`。
- 已核实的数据事实：`platform_product(id, code, title, platform_type, pricing)`；`product_media(product_id, file_type, img_pos, file_url)`，**图片=file_type=1**，img_pos 1-5。
- tokens.store 已实测（2026-09-18）：key 有效；`qwen3.8-max` 视觉/文本可用；`glm-5.3-flash` 是 reasoning 模型，max_tokens 必须 ≥2000；偶发 120s 超时重试即恢复。
- 所有 AI 输出必须 JSON；解析沿用 CreativeToolServiceImpl 的 `indexOf('['/'{')` + `lastIndexOf(']'/'}')` + 去 markdown 围栏法。
- 前端 spzx-admin（Gitee 仓库，与 spzx-parent 不同账号各自提交）：动态菜单机制 = `src/router/modules/kw.js` 导出路由数组 + `router/index.js` import 进 asyncRoutes + `sys_menu.component` 存路由 name + `sys_role_menu` 授权（父菜单 id=38，admin role id=9）。
- 前端验证 = `npm run lint` + `npm run dev`（需 8501 在线）手动过流程。无前端测试框架。
- Prettier：单引号、无分号、printWidth 80。视图 `<style lang="scss">`（自动注入设计令牌）。ProTable `:request` 接收 `{current,size,...}` 返回 `{data,total}`。
- 提交信息 Conventional Commits：`feat(kw): ...`。

---

### Task 1: 数据库初始化脚本（7 表 + 菜单 SQL）

**Files:**
- Create: `spzx-manager/src/main/resources/sql/kw_init.sql`

**Interfaces:**
- Produces: 表 `kw_wordbank_batch`、`kw_wordbank_item`、`kw_product_analysis`、`kw_select_task`、`kw_task_word`、`kw_title_suggestion`、`kw_config`；菜单 component 名 `kwProduct`/`kwWordbank`/`kwTask`（Task 10 前端路由 name 与之一一对应）。

- [ ] **Step 1: 写 SQL 脚本**

```sql
-- kw_init.sql : AI选词推广助手 表结构 + 菜单
-- 库: db_spzx

CREATE TABLE IF NOT EXISTS kw_wordbank_batch (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL COMMENT '批次名，如 睡衣女冬-0918',
  platform_type TINYINT DEFAULT 1 COMMENT '1淘宝 2抖音',
  file_names VARCHAR(500) COMMENT '来源文件名，逗号分隔',
  word_count INT DEFAULT 0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  remark VARCHAR(255)
) COMMENT '词表批次';

CREATE TABLE IF NOT EXISTS kw_wordbank_item (
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
) COMMENT '词表词条';

CREATE TABLE IF NOT EXISTS kw_product_analysis (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  platform_type TINYINT,
  title VARCHAR(100),
  images JSON COMMENT '送AI的图片url列表',
  ai_desc JSON COMMENT '产品拆分描述JSON',
  note VARCHAR(500) COMMENT '用户补充说明(材质/人群等)',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_product (product_id)
) COMMENT 'AI识品结果';

CREATE TABLE IF NOT EXISTS kw_select_task (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id BIGINT NOT NULL,
  batch_id BIGINT NOT NULL,
  analysis_id BIGINT COMMENT '识品结果id，重试时非空则跳过识品',
  note VARCHAR(500) COMMENT '用户补充说明',
  status TINYINT DEFAULT 0 COMMENT '0待跑 1识品中 2选词中 3完成 4失败',
  error_msg VARCHAR(500),
  text_provider VARCHAR(50) COMMENT '本次选词用的引擎',
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  finish_time DATETIME,
  KEY idx_status (status)
) COMMENT '选词任务';

CREATE TABLE IF NOT EXISTS kw_task_word (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  keyword VARCHAR(120) NOT NULL,
  match_score INT COMMENT 'AI匹配度0-100',
  bank_score DECIMAL(8,4) COMMENT '词表得分',
  reason VARCHAR(200) COMMENT 'AI理由',
  picked TINYINT DEFAULT 0 COMMENT '用户勾选',
  KEY idx_task (task_id)
) COMMENT '任务匹配词';

CREATE TABLE IF NOT EXISTS kw_title_suggestion (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id BIGINT NOT NULL,
  title VARCHAR(60) NOT NULL,
  reason VARCHAR(300),
  picked TINYINT DEFAULT 0 COMMENT '用户勾选'
) COMMENT '标题优化建议';

CREATE TABLE IF NOT EXISTS kw_config (
  config_key VARCHAR(50) PRIMARY KEY,
  config_value VARCHAR(50) NOT NULL,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT 'AI引擎运行时配置';

-- 当前引擎（默认全走 tokens-store）
INSERT IGNORE INTO kw_config (config_key, config_value) VALUES ('text_provider', 'tokens-store');
INSERT IGNORE INTO kw_config (config_key, config_value) VALUES ('vision_provider', 'tokens-store');

-- 菜单（父菜单 38=运营管理；component 存前端路由 name）
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI选词商品', 'kwProduct', 60, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='kwProduct');
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI选词词表', 'kwWordbank', 61, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='kwWordbank');
INSERT INTO sys_menu (parent_id, title, component, sort_value, status)
SELECT 38, 'AI选词任务', 'kwTask', 62, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component='kwTask');

-- 授权 admin 角色(role_id=9)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, id FROM sys_menu WHERE component IN ('kwProduct','kwWordbank','kwTask')
AND id NOT IN (SELECT menu_id FROM sys_role_menu WHERE role_id=9);
```

- [ ] **Step 2: 执行并验证**

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx < spzx-manager/src/main/resources/sql/kw_init.sql
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SHOW TABLES LIKE 'kw_%'; SELECT config_key, config_value FROM kw_config; SELECT id,title,component FROM sys_menu WHERE component LIKE 'kw%';"
```

Expected: 7 张 kw_ 表；kw_config 两行 tokens-store；sys_menu 3 行。

- [ ] **Step 3: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-manager/src/main/resources/sql/kw_init.sql && git commit -m "feat(kw): AI选词表结构与菜单初始化脚本"
```

---

### Task 2: 配置层（gitignore + application-local.yml + KwProperties）

**Files:**
- Modify: `.gitignore`（追加一行）
- Create: `spzx-manager/src/main/resources/application-local.yml`
- Modify: `spzx-manager/src/main/resources/application-dev.yml`（顶部加 config import）
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/config/KwProperties.java`

**Interfaces:**
- Produces: `KwProperties`（`@ConfigurationProperties(prefix="kw")`），字段 `Map<String,Provider> providers`、`int topN=2000`、`int batchSize=500`、`int minPopularity=60`、`int imageCount=5`、`int timeoutMs=180000`、`Weights weights`；`Provider{baseUrl, apiKey, visionModel, textModel}`、`Weights{popularity=0.30, clickRate=0.25, convRate=0.25, buyer=0.20}`。后续任务一律经此读配置。

- [ ] **Step 1: .gitignore 追加**

在 `/Users/qyk9527/ideaProject/spzx-parent/.gitignore` 末尾追加：

```gitignore
application-local.yml
```

- [ ] **Step 2: application-local.yml（凭据，永不进 git）**

```yaml
kw:
  providers:
    tokens-store:
      base-url: https://tokens.store/v1
      api-key: ek-hbaWNnV167Xa6YYMbfNfkeLD8vHoE
      vision-model: qwen3.8-max
      text-model: deepseek-v4-flash
    deepseek:
      base-url: https://api.deepseek.com/v1
      api-key: ""
      text-model: deepseek-v4.1-flash
    volcengine-ark:
      base-url: https://ark.cn-beijing.volces.com/api/v3
      api-key: ""
```

- [ ] **Step 3: application-dev.yml 引入 local**

在 `application-dev.yml` 文件**最顶部**（`spring:` 节点之前或该文件已有的顶层结构下）加入顶层键：

```yaml
spring:
  config:
    import: "optional:classpath:application-local.yml"
```

注意：若 `application-dev.yml` 已有 `spring:` 顶层键，把 `config.import` 并入现有 `spring:` 节点，不要写两个 `spring:` 键。

- [ ] **Step 4: KwProperties.java**

```java
package com.joker.spzx.manager.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

@Data
@Component
@ConfigurationProperties(prefix = "kw")
public class KwProperties {

    private Map<String, Provider> providers = new LinkedHashMap<>();
    private int topN = 2000;
    private int batchSize = 500;
    private int minPopularity = 60;
    private int imageCount = 5;
    private int timeoutMs = 180000;
    private Weights weights = new Weights();

    @Data
    public static class Provider {
        private String baseUrl;
        private String apiKey;
        private String visionModel;
        private String textModel;
    }

    @Data
    public static class Weights {
        private double popularity = 0.30;
        private double clickRate = 0.25;
        private double convRate = 0.25;
        private double buyer = 0.20;
    }
}
```

- [ ] **Step 5: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn compile -pl spzx-manager -am -q 2>&1 | tail -5
```

Expected: BUILD SUCCESS（或仅有已知的 3 个预先存在错误之外的自己文件零报错）。

- [ ] **Step 6: 确认 gitignore 生效**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git status --short | grep local
```

Expected: application-local.yml **不出现**在 untracked 列表。

- [ ] **Step 7: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add .gitignore spzx-manager/src/main/resources/application-dev.yml spzx-manager/src/main/java/com/joker/spzx/manager/config/KwProperties.java && git commit -m "feat(kw): 多provider配置层与KwProperties绑定"
```

---

### Task 3: KwConfigService + KwAiClient（多 provider OpenAI 兼容客户端）

**Files:**
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwConfig.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwConfigMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwConfigService.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwAiClient.java`

**Interfaces:**
- Consumes: `KwProperties`（Task 2）。
- Produces:
  - `KwConfigService.getProvider(String key)` → String（key: `"text_provider"`/`"vision_provider"`，DB 无记录默认 `"tokens-store"`）
  - `KwConfigService.setProvider(String key, String value)`
  - `KwAiClient.text(String providerName, String prompt)` → String（文本补全，返回纯 content）
  - `KwAiClient.vision(String providerName, List<Map<String,Object>> contentParts)` → String（contentParts = `[{type:text,...},{type:image_url,...}]`）
  - 两者解析后返回**去围栏的纯文本**（JSON 提取由调用方做）；失败抛 `RuntimeException`（内部已重试 1 次）。

- [ ] **Step 1: KwConfig 实体**

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_config")
public class KwConfig extends Model<KwConfig> {

    @TableId(value = "config_key", type = IdType.INPUT)
    @TableField("config_key")
    private String configKey;

    @TableField("config_value")
    private String configValue;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
```

- [ ] **Step 2: KwConfigMapper**

```java
package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.kw.KwConfig;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface KwConfigMapper extends BaseMapper<KwConfig> {
}
```

- [ ] **Step 3: KwConfigService**

```java
package com.joker.spzx.manager.service.kw;

import com.joker.spzx.manager.mapper.KwConfigMapper;
import com.joker.spzx.model.entity.kw.KwConfig;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class KwConfigService {

    public static final String KEY_TEXT = "text_provider";
    public static final String KEY_VISION = "vision_provider";
    public static final String DEFAULT_PROVIDER = "tokens-store";

    @Autowired
    private KwConfigMapper kwConfigMapper;

    public String getProvider(String key) {
        KwConfig c = kwConfigMapper.selectById(key);
        return c == null || c.getConfigValue() == null || c.getConfigValue().isBlank()
                ? DEFAULT_PROVIDER : c.getConfigValue();
    }

    public void setProvider(String key, String value) {
        KwConfig c = new KwConfig();
        c.setConfigKey(key);
        c.setConfigValue(value);
        if (kwConfigMapper.selectById(key) == null) {
            kwConfigMapper.insert(c);
        } else {
            kwConfigMapper.updateById(c);
        }
        log.info("kw引擎切换: {} -> {}", key, value);
    }
}
```

- [ ] **Step 4: KwAiClient**

```java
package com.joker.spzx.manager.service.kw;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.config.KwProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwAiClient {

    @Autowired
    private KwProperties props;

    @Autowired
    private KwConfigService kwConfigService;

    /** 文本补全（选词/标题） */
    public String text(String providerName, String prompt) {
        JSONArray messages = new JSONArray();
        JSONObject msg = new JSONObject();
        msg.set("role", "user");
        msg.set("content", prompt);
        messages.add(msg);
        return call(providerName, "text", messages);
    }

    /** 视觉补全（识品）：contentParts 为 OpenAI 多模态 content 数组 */
    public String vision(String providerName, List<Map<String, Object>> contentParts) {
        JSONArray messages = new JSONArray();
        JSONObject msg = new JSONObject();
        msg.set("role", "user");
        msg.set("content", contentParts);
        messages.add(msg);
        return call(providerName, "vision", messages);
    }

    private String call(String providerName, String kind, JSONArray messages) {
        KwProperties.Provider p = props.getProviders().get(providerName);
        if (p == null || p.getBaseUrl() == null || p.getApiKey() == null || p.getApiKey().isBlank()) {
            throw new RuntimeException("AI provider 未配置: " + providerName);
        }
        String model = "vision".equals(kind) ? p.getVisionModel() : p.getTextModel();
        if (model == null || model.isBlank()) {
            throw new RuntimeException("provider " + providerName + " 未配置 " + kind + " 模型");
        }
        RuntimeException last = null;
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                JSONObject body = new JSONObject();
                body.set("model", model);
                body.set("messages", messages);
                body.set("temperature", 0.3);
                // reasoning 模型（如 glm-5.3-flash）会先产出思考内容，max_tokens 必须给足
                body.set("max_tokens", 4096);
                String resp = HttpRequest.post(p.getBaseUrl() + "/chat/completions")
                        .header("Authorization", "Bearer " + p.getApiKey())
                        .header("Content-Type", "application/json")
                        .body(body.toString())
                        .timeout(props.getTimeoutMs())
                        .execute()
                        .body();
                JSONObject respJson = JSONUtil.parseObj(resp);
                if (respJson.containsKey("error")) {
                    throw new RuntimeException("AI错误: "
                            + respJson.getJSONObject("error").getStr("message", ""));
                }
                JSONArray choices = respJson.getJSONArray("choices");
                if (choices == null || choices.isEmpty()) {
                    throw new RuntimeException("AI返回空choices");
                }
                String content = choices.getJSONObject(0).getJSONObject("message").getStr("content", "");
                if (content == null || content.isBlank()) {
                    throw new RuntimeException("AI返回空content(可能max_tokens被reasoning耗尽)");
                }
                return stripFence(content.trim());
            } catch (RuntimeException e) {
                last = e;
                log.warn("kw AI调用失败(attempt {}/2, provider={}, model={}): {}",
                        attempt, providerName, model, e.getMessage());
            }
        }
        throw last;
    }

    private String stripFence(String c) {
        return c.replaceAll("^```(json)?", "").replaceAll("```$", "").trim();
    }
}
```

- [ ] **Step 5: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am -q 2>&1 | tail -5
```

Expected: BUILD SUCCESS。

- [ ] **Step 6: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwConfig.java spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwConfigMapper.java spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/ && git commit -m "feat(kw): KwConfigService运行时引擎切换与KwAiClient多provider客户端"
```

---

### Task 4: 实体 + Mapper（词表/任务 6 表）

**Files:**
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwWordbankBatch.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwWordbankItem.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwProductAnalysis.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwSelectTask.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwTaskWord.java`
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwTitleSuggestion.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwWordbankBatchMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwWordbankItemMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwProductAnalysisMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwSelectTaskMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwTaskWordMapper.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwTitleSuggestionMapper.java`

**Interfaces:**
- Produces: 7 个 MyBatis-Plus 实体（含 Task 3 的 KwConfig）与 7 个 `extends BaseMapper<T>` 的 mapper。字段名与 Task 1 的表列一一对应（驼峰）。JSON 列（images/ai_desc）实体中一律 `String` 存原文。所有实体 `extends Model<T>` + `@Data`，风格与 `MallProduct` 一致。

- [ ] **Step 1: 6 个实体**

KwWordbankBatch:

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_wordbank_batch")
public class KwWordbankBatch extends Model<KwWordbankBatch> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("name")
    private String name;

    @TableField("platform_type")
    private Integer platformType;

    @TableField("file_names")
    private String fileNames;

    @TableField("word_count")
    private Integer wordCount;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("remark")
    private String remark;
}
```

KwWordbankItem:

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("kw_wordbank_item")
public class KwWordbankItem extends Model<KwWordbankItem> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("batch_id")
    private Long batchId;

    @TableField("keyword")
    private String keyword;

    @TableField("search_popularity")
    private Integer searchPopularity;

    @TableField("click_rate")
    private BigDecimal clickRate;

    @TableField("conv_rate")
    private BigDecimal convRate;

    @TableField("buyer_count")
    private Integer buyerCount;

    @TableField("score")
    private BigDecimal score;
}
```

KwProductAnalysis:

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_product_analysis")
public class KwProductAnalysis extends Model<KwProductAnalysis> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("product_id")
    private Long productId;

    @TableField("platform_type")
    private Integer platformType;

    @TableField("title")
    private String title;

    @TableField("images")
    private String images;

    @TableField("ai_desc")
    private String aiDesc;

    @TableField("note")
    private String note;

    @TableField("create_time")
    private LocalDateTime createTime;
}
```

KwSelectTask:

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_select_task")
public class KwSelectTask extends Model<KwSelectTask> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("product_id")
    private Long productId;

    @TableField("batch_id")
    private Long batchId;

    @TableField("analysis_id")
    private Long analysisId;

    @TableField("note")
    private String note;

    @TableField("status")
    private Integer status;

    @TableField("error_msg")
    private String errorMsg;

    @TableField("text_provider")
    private String textProvider;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("finish_time")
    private LocalDateTime finishTime;
}
```

KwTaskWord:

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;

@Data
@TableName("kw_task_word")
public class KwTaskWord extends Model<KwTaskWord> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("task_id")
    private Long taskId;

    @TableField("keyword")
    private String keyword;

    @TableField("match_score")
    private Integer matchScore;

    @TableField("bank_score")
    private BigDecimal bankScore;

    @TableField("reason")
    private String reason;

    @TableField("picked")
    private Integer picked;
}
```

KwTitleSuggestion:

```java
package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

@Data
@TableName("kw_title_suggestion")
public class KwTitleSuggestion extends Model<KwTitleSuggestion> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("task_id")
    private Long taskId;

    @TableField("title")
    private String title;

    @TableField("reason")
    private String reason;

    @TableField("picked")
    private Integer picked;
}
```

- [ ] **Step 2: 6 个 Mapper（同一模式）**

每个 mapper 都是这种形态，仅类名/实体名不同：

```java
package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.kw.KwWordbankBatch;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface KwWordbankBatchMapper extends BaseMapper<KwWordbankBatch> {
}
```

按此分别创建：`KwWordbankItemMapper`(KwWordbankItem)、`KwProductAnalysisMapper`(KwProductAnalysis)、`KwSelectTaskMapper`(KwSelectTask)、`KwTaskWordMapper`(KwTaskWord)、`KwTitleSuggestionMapper`(KwTitleSuggestion)。

- [ ] **Step 3: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am -q 2>&1 | tail -5
```

Expected: BUILD SUCCESS。

- [ ] **Step 4: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-model/src/main/java/com/joker/spzx/model/entity/kw/ spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwWordbank*.java spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwProductAnalysisMapper.java spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwSelectTaskMapper.java spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwTaskWordMapper.java spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwTitleSuggestionMapper.java && git commit -m "feat(kw): 词表与任务实体及Mapper"
```

---

### Task 5: 词表解析 + 评分（KwScoreUtil + KwWordbankService）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwScoreUtil.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwWordbankService.java`

**Interfaces:**
- Consumes: `KwProperties`（minPopularity/weights）、`KwWordbankBatchMapper`/`KwWordbankItemMapper`（Task 4）。
- Produces:
  - `KwScoreUtil.score(List<double[]> rows, KwProperties.Weights w)` — 供 service 内部用（rows: `[popularity, clickRate, convRate, buyerCount]`），返回 double[] 得分；min-max 归一化、买家数维度用 `1/(n+1)`。
  - `KwWordbankService.upload(List<MultipartFile> files, String name, Integer platformType)` → Long batchId
  - `KwWordbankService.batchList()` → List<KwWordbankBatch>（按 id desc）
  - `KwWordbankService.itemPage(Long batchId, long pageNum, long pageSize)` → IPage<KwWordbankItem>（score desc）

- [ ] **Step 1: KwScoreUtil（纯函数，无 Spring 依赖）**

```java
package com.joker.spzx.manager.service.kw;

import com.joker.spzx.manager.config.KwProperties;

import java.util.List;

public final class KwScoreUtil {

    private KwScoreUtil() {
    }

    /**
     * 批内 min-max 归一化加权。
     * rows 每行: [popularity, clickRate, convRate, buyerCount]
     * 买家数维度取 1/(n+1)：买家数少=竞争小=得分高。
     * 返回与 rows 等长的得分数组（0-1）。
     */
    public static double[] score(List<double[]> rows, KwProperties.Weights w) {
        int n = rows.size();
        double[] out = new double[n];
        if (n == 0) {
            return out;
        }
        double[] pop = new double[n];
        double[] click = new double[n];
        double[] conv = new double[n];
        double[] buyerInv = new double[n];
        for (int i = 0; i < n; i++) {
            double[] r = rows.get(i);
            pop[i] = r[0];
            click[i] = r[1];
            conv[i] = r[2];
            buyerInv[i] = 1.0 / (r[3] + 1.0);
        }
        for (int i = 0; i < n; i++) {
            out[i] = w.getPopularity() * norm(pop[i], min(pop), max(pop))
                    + w.getClickRate() * norm(click[i], min(click), max(click))
                    + w.getConvRate() * norm(conv[i], min(conv), max(conv))
                    + w.getBuyer() * norm(buyerInv[i], min(buyerInv), max(buyerInv));
        }
        return out;
    }

    private static double norm(double v, double min, double max) {
        return max > min ? (v - min) / (max - min) : 0.5;
    }

    private static double min(double[] a) {
        double m = Double.MAX_VALUE;
        for (double v : a) {
            m = Math.min(m, v);
        }
        return m;
    }

    private static double max(double[] a) {
        double m = -Double.MAX_VALUE;
        for (double v : a) {
            m = Math.max(m, v);
        }
        return m;
    }
}
```

- [ ] **Step 2: KwWordbankService**

```java
package com.joker.spzx.manager.service.kw;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.mapper.KwWordbankBatchMapper;
import com.joker.spzx.manager.mapper.KwWordbankItemMapper;
import com.joker.spzx.model.entity.kw.KwWordbankBatch;
import com.joker.spzx.model.entity.kw.KwWordbankItem;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwWordbankService {

    @Autowired
    private KwWordbankBatchMapper batchMapper;

    @Autowired
    private KwWordbankItemMapper itemMapper;

    @Autowired
    private KwProperties props;

    /**
     * 上传生意参谋导出 Excel（可多文件合并），解析→去重→过滤→打分→入库。
     * 列名宽松映射：表头含关键字即识别。
     */
    public Long upload(List<MultipartFile> files, String name, Integer platformType) {
        // keyword -> item（保持首次出现，人气取更大者）
        Map<String, KwWordbankItem> merged = new LinkedHashMap<>();
        List<String> fileNames = new ArrayList<>();
        try {
            for (MultipartFile f : files) {
                if (f == null || f.isEmpty()) {
                    continue;
                }
                fileNames.add(f.getOriginalFilename());
                parseFile(f, merged);
            }
        } catch (Exception e) {
            throw new RuntimeException("词表解析失败: " + e.getMessage(), e);
        }
        if (merged.isEmpty()) {
            throw new RuntimeException("未解析到任何词条，请检查文件格式（需含关键词/搜索人气列）");
        }

        // 硬过滤：搜索人气 < minPopularity 剔除
        List<KwWordbankItem> items = new ArrayList<>();
        for (KwWordbankItem it : merged.values()) {
            if (it.getSearchPopularity() != null
                    && it.getSearchPopularity() >= props.getMinPopularity()) {
                items.add(it);
            }
        }
        if (items.isEmpty()) {
            throw new RuntimeException("全部词条人气低于 " + props.getMinPopularity() + "，已全部过滤");
        }

        // 批内打分
        List<double[]> rows = new ArrayList<>();
        for (KwWordbankItem it : items) {
            rows.add(new double[]{
                    nz(it.getSearchPopularity()),
                    it.getClickRate() == null ? 0 : it.getClickRate().doubleValue(),
                    it.getConvRate() == null ? 0 : it.getConvRate().doubleValue(),
                    nz(it.getBuyerCount())
            });
        }
        double[] scores = KwScoreUtil.score(rows, props.getWeights());
        for (int i = 0; i < items.size(); i++) {
            items.get(i).setScore(BigDecimal.valueOf(scores[i]).setScale(4, RoundingMode.HALF_UP));
        }
        items.sort((a, b) -> b.getScore().compareTo(a.getScore()));

        // 入库
        KwWordbankBatch batch = new KwWordbankBatch();
        batch.setName(name);
        batch.setPlatformType(platformType == null ? 1 : platformType);
        batch.setFileNames(String.join(",", fileNames));
        batch.setWordCount(items.size());
        batchMapper.insert(batch);
        for (KwWordbankItem it : items) {
            it.setBatchId(batch.getId());
            itemMapper.insert(it);
        }
        log.info("词表批次入库: id={}, name={}, words={}", batch.getId(), name, items.size());
        return batch.getId();
    }

    /** EasyExcel 无模型读：第一行表头，之后每行数据 */
    private void parseFile(MultipartFile f, Map<String, KwWordbankItem> merged) throws Exception {
        EasyExcel.read(f.getInputStream(), new AnalysisEventListenerAdapter(merged)).sheet().doRead();
    }

    private double nz(Integer v) {
        return v == null ? 0 : v;
    }

    public List<KwWordbankBatch> batchList() {
        return batchMapper.selectList(
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<KwWordbankBatch>()
                        .orderByDesc(KwWordbankBatch::getId));
    }

    public IPage<KwWordbankItem> itemPage(Long batchId, long pageNum, long pageSize) {
        return itemMapper.selectPage(new Page<>(pageNum, pageSize),
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<KwWordbankItem>()
                        .eq(KwWordbankItem::getBatchId, batchId)
                        .orderByDesc(KwWordbankItem::getScore));
    }

    /** EasyExcel 监听器：首行表头做列名映射，数据行组装词条 */
    private static class AnalysisEventListenerAdapter
            extends com.alibaba.excel.read.listener.ReadListener<Map<Integer, String>> {

        private final Map<String, Integer> colIdx = new LinkedHashMap<>();
        private final Map<String, Integer> headerMap = new LinkedHashMap<>();
        private final Map<String, KwWordbankItem> merged;
        private int headerRow = -1;

        AnalysisEventListenerAdapter(Map<String, KwWordbankItem> merged) {
            this.merged = merged;
        }

        @Override
        public void invoke(Map<Integer, String> row, com.alibaba.excel.context.AnalysisContext ctx) {
            if (headerRow < 0) {
                // 还没锁定表头：找含"关键词/搜索词"的行
                boolean isHeader = row.values().stream()
                        .anyMatch(v -> v != null && (v.contains("关键词") || v.contains("搜索词")));
                if (!isHeader) {
                    return;
                }
                headerRow = ctx.readRowHolder().getRowIndex();
                row.forEach((k, v) -> {
                    if (v != null && !v.isBlank()) {
                        headerMap.put(v.trim(), k);
                    }
                });
                mapColumns();
                return;
            }
            String kw = str(row, colIdx.get("keyword"));
            if (kw == null || kw.isBlank()) {
                return;
            }
            KwWordbankItem it = new KwWordbankItem();
            it.setKeyword(kw);
            it.setSearchPopularity(intVal(str(row, colIdx.get("popularity"))));
            it.setClickRate(decVal(str(row, colIdx.get("clickRate"))));
            it.setConvRate(decVal(str(row, colIdx.get("convRate"))));
            it.setBuyerCount(intVal(str(row, colIdx.get("buyer"))));
            KwWordbankItem old = merged.get(kw);
            if (old == null || (it.getSearchPopularity() != null
                    && (old.getSearchPopularity() == null
                    || it.getSearchPopularity() > old.getSearchPopularity()))) {
                merged.put(kw, it);
            }
        }

        private void mapColumns() {
            for (Map.Entry<String, Integer> e : headerMap.entrySet()) {
                String h = e.getKey();
                Integer idx = e.getValue();
                if (h.contains("关键词") || h.contains("搜索词")) {
                    colIdx.put("keyword", idx);
                } else if (h.contains("搜索人气") || (h.contains("人气") && !colIdx.containsKey("popularity"))) {
                    colIdx.put("popularity", idx);
                } else if (h.contains("点击率") && !colIdx.containsKey("clickRate")) {
                    colIdx.put("clickRate", idx);
                } else if (h.contains("转化率") && !colIdx.containsKey("convRate")) {
                    colIdx.put("convRate", idx);
                } else if (h.contains("买家数") && !colIdx.containsKey("buyer")) {
                    colIdx.put("buyer", idx);
                }
            }
        }

        private String str(Map<Integer, String> row, Integer idx) {
            return idx == null ? null : row.get(idx);
        }

        private Integer intVal(String s) {
            if (s == null || s.isBlank()) {
                return null;
            }
            try {
                return (int) Double.parseDouble(s.replaceAll("[^0-9.\\-]", ""));
            } catch (Exception e) {
                return null;
            }
        }

        private BigDecimal decVal(String s) {
            if (s == null || s.isBlank()) {
                return null;
            }
            try {
                return new BigDecimal(s.replace("%", "").trim())
                        .divide(new BigDecimal(s.contains("%") ? "100" : "1"), 6, RoundingMode.HALF_UP);
            } catch (Exception e) {
                return null;
            }
        }

        @Override
        public void doAfterAllAnalysed(com.alibaba.excel.context.AnalysisContext ctx) {
        }
    }
}
```

注意：`AnalysisEventListenerAdapter` 用**匿名内部类实现 ReadListener<Map<Integer,String>>**，因为生意参谋导出的列数不定，无模型读最稳。EasyExcel 依赖在 spzx-model pom（Task 0 已核实），spzx-manager 经传递依赖可用；若编译报缺依赖，在 `spzx-manager/pom.xml` 加 `com.alibaba:easyexcel`（版本取 spzx-model 声明）。

- [ ] **Step 3: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn compile -pl spzx-manager -am -q 2>&1 | tail -5
```

Expected: BUILD SUCCESS。

- [ ] **Step 4: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwScoreUtil.java spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwWordbankService.java && git commit -m "feat(kw): 词表Excel解析与四维加权评分"
```

---

### Task 6: 词表 + 商品 Controller（可 curl 验证）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwWordbankController.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwProductController.java`

**Interfaces:**
- Consumes: `KwWordbankService`（Task 5）、`platform_product`/`product_media` 表（直接 MyBatis-Plus 查）。
- Produces（前端 Task 10 的 api/kw.js 按此调用）:
  - `POST /admin/kw/wordbank/upload` — multipart `files[]` + `name` + `platformType`，返回 Result\<Long batchId\>
  - `GET /admin/kw/wordbank/batch/list` → Result\<List\<KwWordbankBatch\>\>
  - `GET /admin/kw/wordbank/batch/{batchId}/items/{pageNum}/{pageSize}` → Result\<IPage\<KwWordbankItem\>\>
  - `GET /admin/kw/product/list/{pageNum}/{pageSize}?keyword=&platformType=` → Result\<IPage\<Map\>\>（含 id/code/title/pricing/platformType/imgUrl 首图）
  - `GET /admin/kw/product/{id}/images` → Result\<List\<String\>\>（≤5 张 file_url）

- [ ] **Step 1: KwWordbankController**

```java
package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.kw.KwWordbankService;
import com.joker.spzx.model.entity.kw.KwWordbankBatch;
import com.joker.spzx.model.entity.kw.KwWordbankItem;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/admin/kw/wordbank")
public class KwWordbankController {

    @Autowired
    private KwWordbankService kwWordbankService;

    @PostMapping("/upload")
    public Result<Long> upload(@RequestParam("files") List<MultipartFile> files,
                               @RequestParam("name") String name,
                               @RequestParam(value = "platformType", required = false) Integer platformType) {
        return Result.build(kwWordbankService.upload(files, name, platformType));
    }

    @GetMapping("/batch/list")
    public Result<List<KwWordbankBatch>> batchList() {
        return Result.build(kwWordbankService.batchList());
    }

    @GetMapping("/batch/{batchId}/items/{pageNum}/{pageSize}")
    public Result<IPage<KwWordbankItem>> items(@PathVariable Long batchId,
                                               @PathVariable long pageNum,
                                               @PathVariable long pageSize) {
        return Result.build(kwWordbankService.itemPage(batchId, pageNum, pageSize));
    }
}
```

- [ ] **Step 2: KwProductController**

```java
package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.model.entity.oper.MallProduct;
import com.joker.spzx.model.entity.oper.ProductMedia;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/admin/kw/product")
public class KwProductController {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @GetMapping("/list/{pageNum}/{pageSize}")
    public Result<IPage<Map<String, Object>>> list(@PathVariable long pageNum,
                                                   @PathVariable long pageSize,
                                                   @RequestParam(required = false) String keyword,
                                                   @RequestParam(required = false) Integer platformType) {
        StringBuilder where = new StringBuilder("WHERE 1=1");
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND title LIKE '%").append(keyword.replace("'", "''")).append("%'");
        }
        if (platformType != null) {
            where.append(" AND platform_type=").append(platformType);
        }
        long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM platform_product " + where, Long.class);
        long offset = (pageNum - 1) * pageSize;
        List<Map<String, Object>> records = jdbcTemplate.queryForList(
                "SELECT p.id, p.code, p.title, p.pricing, p.platform_type platformType, "
                        + "(SELECT m.file_url FROM product_media m WHERE m.product_id=p.id "
                        + "  AND m.file_type=1 ORDER BY m.img_pos LIMIT 1) imgUrl "
                        + "FROM platform_product p " + where
                        + " ORDER BY p.id DESC LIMIT " + pageSize + " OFFSET " + offset);
        Map<String, Object> page = new LinkedHashMap<>();
        page.put("records", records);
        page.put("total", total);
        page.put("current", pageNum);
        page.put("size", pageSize);
        // Result<IPage> 泛型仅作声明，前端只读 records/total，此处用 Page 承载
        Page<Map<String, Object>> p = new Page<>(pageNum, pageSize, total);
        p.setRecords(records);
        return Result.build(p);
    }

    @GetMapping("/{id}/images")
    public Result<List<String>> images(@PathVariable Long id) {
        List<String> urls = jdbcTemplate.queryForList(
                "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 "
                        + "ORDER BY img_pos LIMIT 5", String.class, id);
        return Result.build(urls);
    }
}
```

说明：商品列表直接 JdbcTemplate 拼 SQL（只读、字段固定、keyword 已做单引号转义），不新建 entity，避免为两列查询建整套 mapper。`MallProduct`/`ProductMedia` 的 import 若未用到请删除（此实现实际未用）。

- [ ] **Step 3: 编译 + 启动 + curl 验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn compile -pl spzx-manager -am -q
# 确认 MySQL/Redis 在线
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SELECT 1"
redis-cli ping
# 启动后端（后台运行）
nohup mvn spring-boot:run -pl spzx-manager > /tmp/spzx-8501.log 2>&1 &
# 等待就绪（看到 Started ManagerApplication）
grep -c "Started ManagerApplication" /tmp/spzx-8501.log
```

curl 实测（先用 venv 生成一个两行的测试 Excel）：

```bash
/Users/qyk9527/tb-auto/venv/bin/python - <<'EOF'
from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["搜索词", "搜索人气", "点击率", "支付转化率", "买家数"])
ws.append(["睡衣女秋冬", "8200", "5.2%", "3.1%", "120"])
ws.append(["家居服套装", "6100", "4.8%", "2.7%", "95"])
ws.append(["睡衣女童", "300", "2.0%", "1.0%", "10"])
wb.save("/tmp/kw_test.xlsx")
EOF
# 登录拿 token（参照现有后台登录方式，admin/验证码；或从浏览器 localStorage['VEA-TOKEN'] 取）
TOKEN="<从3001前端登录后localStorage取>"
curl -s "http://127.0.0.1:8501/admin/kw/product/list/1/10?keyword=睡衣" -H "token: $TOKEN"
curl -s -X POST "http://127.0.0.1:8501/admin/kw/wordbank/upload" -H "token: $TOKEN" \
  -F "files[]=@/tmp/kw_test.xlsx" -F "name=测试词表0918" -F "platformType=1"
curl -s "http://127.0.0.1:8501/admin/kw/wordbank/batch/list" -H "token: $TOKEN"
curl -s "http://127.0.0.1:8501/admin/kw/wordbank/batch/1/items/1/10" -H "token: $TOKEN"
```

Expected: product/list 返回 records 含 imgUrl；upload 返回 batchId；items 返回 3 词按 score 降序、无"睡衣女童"（人气 300≥60 不会被过滤——注意 minPopularity=60，300 会保留；此处验证的是解析与打分）。

mysql 复核：

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SELECT keyword, search_popularity, score FROM kw_wordbank_item ORDER BY score DESC"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwWordbankController.java spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwProductController.java && git commit -m "feat(kw): 词表上传与商品选择接口"
```

---

### Task 7: 任务 Service（识品→选词→标题异步状态机）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwTaskService.java`

**Interfaces:**
- Consumes: `KwAiClient`/`KwConfigService`（Task 3）、`KwProperties`（Task 2）、Task 4 全部 mapper、`JdbcTemplate`（查商品/图/词表）。
- Produces:
  - `KwTaskService.create(Long productId, Long batchId, String note)` → Long taskId
  - `KwTaskService.detail(Long taskId)` → Map（task + words + titles + profile + productTitle）
  - `KwTaskService.retry(Long taskId)`（status 4→0 重入队；analysis_id 非空则跳过识品）
  - `KwTaskService.pickWords(Long taskId, List<Long> wordIds)` / `KwTaskService.pickTitles(Long taskId, List<Long> titleIds)`
  - 内部线程池（1 核心线程队列 100）串行执行，AI 不并发轰炸。

- [ ] **Step 1: KwTaskService 完整实现**

```java
package com.joker.spzx.manager.service.kw;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.mapper.*;
import com.joker.spzx.model.entity.kw.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class KwTaskService {

    public static final int ST_PENDING = 0, ST_PROFILE = 1, ST_SELECT = 2, ST_DONE = 3, ST_FAIL = 4;

    private static final ThreadPoolExecutor POOL = new ThreadPoolExecutor(
            1, 1, 60, TimeUnit.SECONDS, new LinkedBlockingQueue<>(100),
            r -> {
                Thread t = new Thread(r, "kw-task");
                t.setDaemon(true);
                return t;
            });

    @Autowired private KwSelectTaskMapper taskMapper;
    @Autowired private KwTaskWordMapper wordMapper;
    @Autowired private KwTitleSuggestionMapper titleMapper;
    @Autowired private KwProductAnalysisMapper analysisMapper;
    @Autowired private KwWordbankItemMapper wordbankItemMapper;
    @Autowired private KwAiClient aiClient;
    @Autowired private KwConfigService configService;
    @Autowired private KwProperties props;
    @Autowired private JdbcTemplate jdbcTemplate;

    public Long create(Long productId, Long batchId, String note) {
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT id, code, title, platform_type FROM platform_product WHERE id=?", productId);
        KwSelectTask task = new KwSelectTask();
        task.setProductId(productId);
        task.setBatchId(batchId);
        task.setNote(note);
        task.setStatus(ST_PENDING);
        task.setTextProvider(configService.getProvider(KwConfigService.KEY_TEXT));
        taskMapper.insert(task);
        submit(task.getId());
        return task.getId();
    }

    public void retry(Long taskId) {
        KwSelectTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new RuntimeException("任务不存在");
        }
        if (task.getStatus() != ST_FAIL) {
            throw new RuntimeException("仅失败任务可重试");
        }
        task.setStatus(ST_PENDING);
        task.setErrorMsg(null);
        task.setTextProvider(configService.getProvider(KwConfigService.KEY_TEXT));
        taskMapper.updateById(task);
        submit(taskId);
    }

    private void submit(Long taskId) {
        POOL.execute(() -> run(taskId));
    }

    private void run(Long taskId) {
        try {
            KwSelectTask task = taskMapper.selectById(taskId);
            if (task == null) {
                return;
            }
            Long analysisId = task.getAnalysisId();
            JSONObject profile;
            if (analysisId == null) {
                // ② 识品
                task.setStatus(ST_PROFILE);
                taskMapper.updateById(task);
                profile = doProfile(task);
                KwProductAnalysis an = new KwProductAnalysis();
                an.setProductId(task.getProductId());
                Map<String, Object> product = jdbcTemplate.queryForMap(
                        "SELECT platform_type, title FROM platform_product WHERE id=?", task.getProductId());
                an.setPlatformType((Integer) product.get("platform_type"));
                an.setTitle((String) product.get("title"));
                List<String> imgs = jdbcTemplate.queryForList(
                        "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 "
                                + "ORDER BY img_pos LIMIT " + props.getImageCount(), String.class, task.getProductId());
                an.setImages(JSONUtil.toJsonStr(imgs));
                an.setAiDesc(profile.toString());
                an.setNote(task.getNote());
                analysisMapper.insert(an);
                task.setAnalysisId(an.getId());
                taskMapper.updateById(task);
            } else {
                profile = JSONUtil.parseObj(analysisMapper.selectById(analysisId).getAiDesc());
            }
            // ③ 选词
            task.setStatus(ST_SELECT);
            taskMapper.updateById(task);
            doSelect(task, profile);
            // 标题
            doTitles(task, profile);
            task.setStatus(ST_DONE);
            task.setFinishTime(LocalDateTime.now());
            taskMapper.updateById(task);
            log.info("kw任务完成: id={}", taskId);
        } catch (Exception e) {
            log.error("kw任务失败: id={}", taskId, e);
            KwSelectTask task = taskMapper.selectById(taskId);
            if (task != null) {
                task.setStatus(ST_FAIL);
                String msg = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
                task.setErrorMsg(msg.length() > 490 ? msg.substring(0, 490) : msg);
                taskMapper.updateById(task);
            }
        }
    }

    private JSONObject doProfile(KwSelectTask task) {
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT title, platform_type FROM platform_product WHERE id=?", task.getProductId());
        String title = String.valueOf(product.get("title"));
        List<String> imgs = jdbcTemplate.queryForList(
                "SELECT file_url FROM product_media WHERE product_id=? AND file_type=1 "
                        + "ORDER BY img_pos LIMIT " + props.getImageCount(), String.class, task.getProductId());
        StringBuilder sb = new StringBuilder();
        sb.append("你是电商选品专家。根据商品图和标题分析产品，输出严格JSON：\n");
        sb.append("{\"category\":\"叶子类目\",\"material\":\"材质\",\"fit\":\"版型\",");
        sb.append("\"audience\":{\"gender\":\"\",\"age\":\"\",\"scene\":\"\"},\"style\":\"风格\",");
        sb.append("\"season\":\"季节\",\"selling_points\":[\"卖点\"],");
        sb.append("\"exclude_dims\":[{\"dim\":\"维度名\",\"avoid_keywords\":[\"排除词\"]}],");
        sb.append("\"seed_keywords\":[\"品类核心词\"]}\n");
        sb.append("规则：\n");
        sb.append("1. audience 填目标人群（性别/年龄段/使用场景）\n");
        sb.append("2. exclude_dims 列出该产品不应触达的人群/场景维度及对应关键词（如成人商品排除\"儿童,童,学生\"），2-4 条\n");
        sb.append("3. seed_keywords 列 5-10 个品类核心词\n");
        sb.append("4. 只输出 JSON，不要解释\n");
        sb.append("商品标题：").append(title).append("\n");
        if (task.getNote() != null && !task.getNote().isBlank()) {
            sb.append("补充说明：").append(task.getNote()).append("\n");
        }
        List<Map<String, Object>> parts = new ArrayList<>();
        Map<String, Object> textPart = new LinkedHashMap<>();
        textPart.put("type", "text");
        textPart.put("text", sb.toString());
        parts.add(textPart);
        for (String url : imgs) {
            Map<String, Object> imgPart = new LinkedHashMap<>();
            imgPart.put("type", "image_url");
            Map<String, Object> inner = new LinkedHashMap<>();
            inner.put("url", url);
            imgPart.put("image_url", inner);
            parts.add(imgPart);
        }
        String provider = configService.getProvider(KwConfigService.KEY_VISION);
        String content = aiClient.vision(provider, parts);
        int s = content.indexOf('{');
        int e = content.lastIndexOf('}');
        if (s < 0 || e <= s) {
            throw new RuntimeException("识品返回非JSON: " + content.substring(0, Math.min(100, content.length())));
        }
        return JSONUtil.parseObj(content.substring(s, e + 1));
    }

    private void doSelect(KwSelectTask task, JSONObject profile) {
        // 收集排除关键词
        List<String> avoid = new ArrayList<>();
        JSONArray dims = profile.getJSONArray("exclude_dims");
        if (dims != null) {
            for (Object o : dims) {
                JSONArray kws = ((JSONObject) o).getJSONArray("avoid_keywords");
                if (kws != null) {
                    for (Object k : kws) {
                        avoid.add(String.valueOf(k));
                    }
                }
            }
        }
        // 粗筛 + TopN
        List<KwWordbankItem> bank = wordbankItemMapper.selectList(
                new LambdaQueryWrapper<KwWordbankItem>()
                        .eq(KwWordbankItem::getBatchId, task.getBatchId())
                        .orderByDesc(KwWordbankItem::getScore)
                        .last("LIMIT " + props.getTopN()));
        List<KwWordbankItem> filtered = new ArrayList<>();
        for (KwWordbankItem it : bank) {
            boolean bad = false;
            for (String a : avoid) {
                if (!a.isBlank() && it.getKeyword().contains(a)) {
                    bad = true;
                    break;
                }
            }
            if (!bad) {
                filtered.add(it);
            }
        }
        Map<String, BigDecimal> bankScores = new HashMap<>();
        for (KwWordbankItem it : filtered) {
            bankScores.put(it.getKeyword(), it.getScore());
        }
        // 分批
        int batch = props.getBatchSize();
        List<String> profileJson = List.of(profile.toString());
        for (int i = 0; i < filtered.size(); i += batch) {
            List<KwWordbankItem> chunk = filtered.subList(i, Math.min(i + batch, filtered.size()));
            StringBuilder wordLines = new StringBuilder();
            for (KwWordbankItem it : chunk) {
                wordLines.append(it.getKeyword()).append("|")
                        .append(nz(it.getSearchPopularity())).append("|")
                        .append(it.getClickRate() == null ? 0 : it.getClickRate()).append("|")
                        .append(it.getConvRate() == null ? 0 : it.getConvRate()).append("|")
                        .append(nz(it.getBuyerCount())).append("\n");
            }
            String prompt = "你是淘宝付费推广选词专家。产品画像JSON：\n" + profile.getStr("profile", profile.toString())
                    + "\n候选词列表（关键词|搜索人气|点击率|转化率|买家数）：\n" + wordLines
                    + "\n任务：为该产品评估每个词的匹配度。match_score 0-100：完全契合人群/品类/卖点给 80 以上，沾边 50-79，不匹配低于 50（仍要输出，不要删词）。\n"
                    + "reason 用一句话说明匹配或不匹配的原因。\n"
                    + "只输出 JSON 数组 [{\"keyword\":\"词\",\"match_score\":85,\"reason\":\"一句话\"}]，不要输出其他内容。";
            String provider = configService.getProvider(KwConfigService.KEY_TEXT);
            String content = aiClient.text(provider, prompt);
            int s = content.indexOf('[');
            int e = content.lastIndexOf(']');
            if (s < 0 || e <= s) {
                throw new RuntimeException("选词返回非JSON(批 " + (i / batch + 1) + ")");
            }
            JSONArray arr = JSONUtil.parseArray(content.substring(s, e + 1));
            for (Object o : arr) {
                JSONObject w = (JSONObject) o;
                String kw = w.getStr("keyword", "").trim();
                if (kw.isEmpty() || !bankScores.containsKey(kw)) {
                    continue;
                }
                KwTaskWord tw = new KwTaskWord();
                tw.setTaskId(task.getId());
                tw.setKeyword(kw);
                tw.setMatchScore(w.getInt("match_score", 0));
                tw.setBankScore(bankScores.get(kw));
                String reason = w.getStr("reason", "");
                tw.setReason(reason.length() > 190 ? reason.substring(0, 190) : reason);
                tw.setPicked(0);
                wordMapper.insert(tw);
            }
        }
    }

    private void doTitles(KwSelectTask task, JSONObject profile) {
        List<KwTaskWord> top = wordMapper.selectList(
                new LambdaQueryWrapper<KwTaskWord>()
                        .eq(KwTaskWord::getTaskId, task.getId())
                        .orderByDesc(KwTaskWord::getMatchScore)
                        .last("LIMIT 30"));
        if (top.isEmpty()) {
            return;
        }
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT title FROM platform_product WHERE id=?", task.getProductId());
        StringBuilder words = new StringBuilder();
        for (KwTaskWord w : top) {
            words.append(w.getKeyword()).append("(").append(w.getMatchScore()).append(") ");
        }
        String prompt = "你是淘宝标题优化专家。原标题：" + product.get("title")
                + "\n产品画像：" + profile
                + "\n高分匹配词（按匹配度排序）：" + words
                + "\n生成 3 个优化标题：\n"
                + "1. 每个不超过 30 个汉字\n"
                + "2. 自然融入高分词，不堆砌、不无意义重复\n"
                + "3. 不含广告法违禁词（最/第一/顶级/极致/100%等一律不用）\n"
                + "4. 空格分隔不同卖点短语\n"
                + "只输出 JSON 数组 [{\"title\":\"...\",\"reason\":\"一句话\"}]。";
        String provider = configService.getProvider(KwConfigService.KEY_TEXT);
        String content = aiClient.text(provider, prompt);
        int s = content.indexOf('[');
        int e = content.lastIndexOf(']');
        if (s < 0 || e <= s) {
            return; // 标题是加分项，失败不致命
        }
        JSONArray arr = JSONUtil.parseArray(content.substring(s, e + 1));
        for (Object o : arr) {
            JSONObject t = (JSONObject) o;
            String title = t.getStr("title", "").trim();
            if (title.isEmpty() || title.length() > 60) {
                continue;
            }
            KwTitleSuggestion ts = new KwTitleSuggestion();
            ts.setTaskId(task.getId());
            ts.setTitle(title);
            ts.setReason(t.getStr("reason", ""));
            titleMapper.insert(ts);
        }
    }

    public Map<String, Object> detail(Long taskId) {
        KwSelectTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new RuntimeException("任务不存在");
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("task", task);
        Map<String, Object> product = jdbcTemplate.queryForMap(
                "SELECT code, title, pricing FROM platform_product WHERE id=?", task.getProductId());
        out.put("productTitle", product.get("title"));
        out.put("productCode", product.get("code"));
        if (task.getAnalysisId() != null) {
            KwProductAnalysis an = analysisMapper.selectById(task.getAnalysisId());
            out.put("profile", an == null ? null : an.getAiDesc());
        }
        out.put("words", wordMapper.selectList(new LambdaQueryWrapper<KwTaskWord>()
                .eq(KwTaskWord::getTaskId, taskId)
                .orderByDesc(KwTaskWord::getMatchScore)));
        out.put("titles", titleMapper.selectList(new LambdaQueryWrapper<KwTitleSuggestion>()
                .eq(KwTitleSuggestion::getTaskId, taskId)));
        return out;
    }

    public void pickWords(Long taskId, List<Long> wordIds) {
        for (Long id : wordIds) {
            KwTaskWord w = wordMapper.selectById(id);
            if (w != null && w.getTaskId().equals(taskId)) {
                w.setPicked(w.getPicked() != null && w.getPicked() == 1 ? 0 : 1);
                wordMapper.updateById(w);
            }
        }
    }

    public void pickTitles(Long taskId, List<Long> titleIds) {
        for (Long id : titleIds) {
            KwTitleSuggestion t = titleMapper.selectById(id);
            if (t != null && t.getTaskId().equals(taskId)) {
                t.setPicked(t.getPicked() != null && t.getPicked() == 1 ? 0 : 1);
                titleMapper.updateById(t);
            }
        }
    }

    private int nz(Integer v) {
        return v == null ? 0 : v;
    }
}
```

实现细节说明：
- `doSelect` 里 prompt 第一行直接用 `profile.toString()`。
- `KwTitleSuggestion` 实体含 `picked` 字段（Task 1 DDL 已含该列）。

- [ ] **Step 2: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn compile -pl spzx-manager -am -q 2>&1 | tail -5
```

Expected: BUILD SUCCESS。

- [ ] **Step 3: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwTaskService.java && git commit -m "feat(kw): 识品选词标题异步任务状态机"
```

---

### Task 8: 任务 Controller + 引擎配置接口（全链路 curl）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwTaskController.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwConfigController.java`

**Interfaces:**
- Consumes: `KwTaskService`（Task 7）、`KwConfigService`（Task 3）、`KwProperties`（Task 2）。
- Produces（前端调用契约）:
  - `POST /admin/kw/task/create` body `{productId, batchId, note}` → Result\<Long taskId\>
  - `GET /admin/kw/task/list/{pageNum}/{pageSize}?status=` → Result\<IPage\<KwSelectTask\>\>（id desc）
  - `GET /admin/kw/task/{id}` → Result\<Map\>（Task 7 detail）
  - `POST /admin/kw/task/{id}/retry`
  - `POST /admin/kw/task/{id}/pick` body `{wordIds: [], titleIds: []}`（两者至少一个非空）
  - `GET /admin/kw/config` → Result\<Map\> `{textProvider, visionProvider, providers:[{name, hasKey, visionModel, textModel}]}`
  - `PUT /admin/kw/config` body `{textProvider}` → 校验 provider 存在且 key 非空，否则 400 语义错误返回 Result 失败

- [ ] **Step 1: KwTaskController**

```java
package com.joker.spzx.manager.controller;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.kw.KwTaskService;
import com.joker.spzx.model.entity.kw.KwSelectTask;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/task")
public class KwTaskController {

    @Autowired
    private KwTaskService kwTaskService;

    public record PickDto(List<Long> wordIds, List<Long> titleIds) {
    }

    public record CreateDto(Long productId, Long batchId, String note) {
    }

    @PostMapping("/create")
    public Result<Long> create(@RequestBody CreateDto dto) {
        if (dto.productId() == null || dto.batchId() == null) {
            return Result.build(null, 204, "productId/batchId 必填");
        }
        return Result.build(kwTaskService.create(dto.productId(), dto.batchId(), dto.note()));
    }

    @GetMapping("/list/{pageNum}/{pageSize}")
    public Result<IPage<KwSelectTask>> list(@PathVariable long pageNum,
                                            @PathVariable long pageSize,
                                            @RequestParam(required = false) Integer status) {
        LambdaQueryWrapper<KwSelectTask> qw = new LambdaQueryWrapper<KwSelectTask>()
                .orderByDesc(KwSelectTask::getId);
        if (status != null) {
            qw.eq(KwSelectTask::getStatus, status);
        }
        return Result.build(kwTaskService.getTaskMapper().selectPage(new Page<>(pageNum, pageSize), qw));
    }

    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable Long id) {
        return Result.build(kwTaskService.detail(id));
    }

    @PostMapping("/{id}/retry")
    public Result<Void> retry(@PathVariable Long id) {
        kwTaskService.retry(id);
        return Result.build(null);
    }

    @PostMapping("/{id}/pick")
    public Result<Void> pick(@PathVariable Long id, @RequestBody PickDto dto) {
        if (dto.wordIds() != null && !dto.wordIds().isEmpty()) {
            kwTaskService.pickWords(id, dto.wordIds());
        }
        if (dto.titleIds() != null && !dto.titleIds().isEmpty()) {
            kwTaskService.pickTitles(id, dto.titleIds());
        }
        return Result.build(null);
    }
}
```

（注：已核实 `Result` 类真实 API——只有 `build(T)` / `build(T, Integer, String)` / `build(T, ResultCodeEnum)` 三个静态方法，无链式调用。错误返回一律 `Result.build(null, 204, "消息")`，前端 request.js 以 code===200 为成功、208 为未登录。另外 `list` 用到 `kwTaskService.getTaskMapper()`，需在 KwTaskService 补：`public KwSelectTaskMapper getTaskMapper() { return taskMapper; }`）

- [ ] **Step 2: KwConfigController**

```java
package com.joker.spzx.manager.controller;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequestMapping("/admin/kw/config")
public class KwConfigController {

    @Autowired
    private KwConfigService kwConfigService;

    @Autowired
    private KwProperties props;

    public record SetDto(String textProvider) {
    }

    @GetMapping
    public Result<Map<String, Object>> get() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("textProvider", kwConfigService.getProvider(KwConfigService.KEY_TEXT));
        out.put("visionProvider", kwConfigService.getProvider(KwConfigService.KEY_VISION));
        List<Map<String, Object>> providers = new ArrayList<>();
        for (Map.Entry<String, KwProperties.Provider> e : props.getProviders().entrySet()) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("name", e.getKey());
            p.put("hasKey", e.getValue().getApiKey() != null && !e.getValue().getApiKey().isBlank());
            p.put("visionModel", e.getValue().getVisionModel());
            p.put("textModel", e.getValue().getTextModel());
            providers.add(p);
        }
        out.put("providers", providers);
        return Result.build(out);
    }

    @PutMapping
    public Result<Void> set(@RequestBody SetDto dto) {
        String name = dto.textProvider();
        KwProperties.Provider p = props.getProviders().get(name);
        if (p == null || p.getApiKey() == null || p.getApiKey().isBlank()) {
            return Result.build(null, 204, "provider 不存在或 key 未配置: " + name);
        }
        kwConfigService.setProvider(KwConfigService.KEY_TEXT, name);
        return Result.build(null);
    }
}
```

（同 Task 8 Step 1 的 Result API 注。）

- [ ] **Step 3: 重启后端 + 全链路 curl（真实跑一单）**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent
# 若 8501 在跑先停掉再起
lsof -ti:8501 | xargs kill -9 2>/dev/null
mvn spring-boot:run -pl spzx-manager > /tmp/spzx-8501.log 2>&1 &
# 就绪后：
TOKEN="<登录token>"
# 1. 引擎配置
curl -s "http://127.0.0.1:8501/admin/kw/config" -H "token: $TOKEN"
# 2. 切到不存在的 provider 应被拒
curl -s -X PUT "http://127.0.0.1:8501/admin/kw/config" -H "token: $TOKEN" \
  -H "Content-Type: application/json" -d '{"textProvider":"nope"}'
# 3. 创建任务（productId 用 product/list 里挑一个真实商品）
curl -s -X POST "http://127.0.0.1:8501/admin/kw/task/create" -H "token: $TOKEN" \
  -H "Content-Type: application/json" -d '{"productId":123,"batchId":1,"note":"女款 秋冬"}'
# 4. 轮询（识品 10-30s、选词 1-3min）
curl -s "http://127.0.0.1:8501/admin/kw/task/1" -H "token: $TOKEN" | /Users/qyk9527/tb-auto/venv/bin/python -m json.tool | head -40
```

Expected: 任务状态 0→1→2→3；detail 里 words 非空、match_score 有梯度、reason 是人话、无"童"类排除词混入；titles 3 条。

- [ ] **Step 4: mysql 复核 + Commit**

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e \
  "SELECT status, error_msg, text_provider FROM kw_select_task ORDER BY id DESC LIMIT 3; SELECT COUNT(*) words, MAX(match_score) top FROM kw_task_word WHERE task_id=1"
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwTaskController.java spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwConfigController.java spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwTaskService.java && git commit -m "feat(kw): 任务与引擎配置接口"
```

---

### Task 9: 导出 xlsx

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwExportService.java`
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwTaskController.java`（加 export 端点）

**Interfaces:**
- Produces: `GET /admin/kw/task/{id}/export` → xlsx 文件流（sheet1 词：关键词/匹配度/词表得分/理由/是否勾选；sheet2 标题：标题/理由）。

- [ ] **Step 1: KwExportService**

```java
package com.joker.spzx.manager.service.kw;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.mapper.KwTaskWordMapper;
import com.joker.spzx.manager.mapper.KwTitleSuggestionMapper;
import com.joker.spzx.model.entity.kw.KwTaskWord;
import com.joker.spzx.model.entity.kw.KwTitleSuggestion;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import jakarta.servlet.http.HttpServletResponse;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.*;

@Service
public class KwExportService {

    @Autowired
    private KwTaskWordMapper wordMapper;

    @Autowired
    private KwTitleSuggestionMapper titleMapper;

    public record WordRow(String keyword, Integer matchScore, java.math.BigDecimal bankScore,
                          String reason, String picked) {
    }

    public record TitleRow(String title, String reason) {
    }

    public void export(Long taskId, HttpServletResponse response) throws Exception {
        List<WordRow> words = new ArrayList<>();
        for (KwTaskWord w : wordMapper.selectList(new LambdaQueryWrapper<KwTaskWord>()
                .eq(KwTaskWord::getTaskId, taskId)
                .orderByDesc(KwTaskWord::getMatchScore))) {
            words.add(new WordRow(w.getKeyword(), w.getMatchScore(), w.getBankScore(),
                    w.getReason(), w.getPicked() != null && w.getPicked() == 1 ? "是" : "否"));
        }
        List<TitleRow> titles = new ArrayList<>();
        for (KwTitleSuggestion t : titleMapper.selectList(new LambdaQueryWrapper<KwTitleSuggestion>()
                .eq(KwTitleSuggestion::getTaskId, taskId))) {
            titles.add(new TitleRow(t.getTitle(), t.getReason()));
        }
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("kw_task_" + taskId, StandardCharsets.UTF_8);
        response.setHeader("Content-Disposition", "attachment;filename=" + fileName + ".xlsx");
        try (com.alibaba.excel.ExcelWriter writer = new com.alibaba.excel.ExcelWriter(
                response.getOutputStream())) {
            com.alibaba.excel.write.metadata.WriteSheet s1 = EasyExcel.writerSheet(0, "匹配词")
                    .head(WordRow.class).build();
            com.alibaba.excel.write.metadata.WriteSheet s2 = EasyExcel.writerSheet(1, "标题建议")
                    .head(TitleRow.class).build();
            writer.write(words, s1);
            writer.write(titles, s2);
        }
    }
}
```

- [ ] **Step 2: KwTaskController 加端点**

在 KwTaskController 内追加：

```java
@Autowired
private com.joker.spzx.manager.service.kw.KwExportService kwExportService;

@GetMapping("/{id}/export")
public void export(@PathVariable Long id, jakarta.servlet.http.HttpServletResponse response) throws Exception {
    kwExportService.export(id, response);
}
```

- [ ] **Step 3: 编译 + curl 验证文件**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn compile -pl spzx-manager -am -q
# 重启 8501 后：
TOKEN="<登录token>"
curl -s -o /tmp/kw_export.xlsx "http://127.0.0.1:8501/admin/kw/task/1/export" -H "token: $TOKEN"
/Users/qyk9527/tb-auto/venv/bin/python -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/kw_export.xlsx')
print(wb.sheetnames)
ws = wb['匹配词']
print('rows:', ws.max_row, 'cols:', ws.max_column)
print([c.value for c in ws[1]])
"
```

Expected: sheetnames `['匹配词', '标题建议']`；表头 `keyword/matchScore/...`（EasyExcel 默认用字段名做表头；如需中文表头在 record 字段加 `@com.alibaba.excel.annotation.ExcelProperty("关键词")` 注解——推荐直接加注解：关键词/匹配度/词表得分/理由/已勾选）。

- [ ] **Step 4: Commit**

```bash
cd /Users/qyk9527/ideaProject/spzx-parent && git add spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwExportService.java spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwTaskController.java && git commit -m "feat(kw): 任务结果导出xlsx"
```

---

### Task 10: 前端 api + 路由 + 菜单联动

**Files:**
- Create: `spzx-admin/src/api/kw.js`
- Create: `spzx-admin/src/router/modules/kw.js`
- Modify: `spzx-admin/src/router/index.js`（import kw + 加入 asyncRoutes）

**Interfaces:**
- Consumes: Task 6/8 的后端接口路径；sys_menu 已有 component=`kwProduct`/`kwWordbank`/`kwTask`（Task 1）。
- Produces: 路由 name `kwProduct`/`kwWordbank`/`kwTask`（与 sys_menu.component 严格一致，动态菜单按 name 过滤）。

- [ ] **Step 1: src/api/kw.js**

```javascript
import request from '@/utils/request'

const api_name = '/admin/kw'

// ============ 商品 ============
export const GetKwProductPage = (pageNum, pageSize, queryDto) => {
  return request({
    url: `${api_name}/product/list/${pageNum}/${pageSize}`,
    method: 'get',
    params: queryDto,
  })
}

export const GetKwProductImages = (id) => {
  return request({
    url: `${api_name}/product/${id}/images`,
    method: 'get',
  })
}

// ============ 词表 ============
export const UploadWordbank = (formData) => {
  return request({
    url: `${api_name}/wordbank/upload`,
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const GetWordbankBatchList = () => {
  return request({
    url: `${api_name}/wordbank/batch/list`,
    method: 'get',
  })
}

export const GetWordbankItems = (batchId, pageNum, pageSize) => {
  return request({
    url: `${api_name}/wordbank/batch/${batchId}/items/${pageNum}/${pageSize}`,
    method: 'get',
  })
}

// ============ 任务 ============
export const CreateKwTask = (data) => {
  return request({
    url: `${api_name}/task/create`,
    method: 'post',
    data,
  })
}

export const GetKwTaskPage = (pageNum, pageSize, queryDto) => {
  return request({
    url: `${api_name}/task/list/${pageNum}/${pageSize}`,
    method: 'get',
    params: queryDto,
  })
}

export const GetKwTaskDetail = (id) => {
  return request({
    url: `${api_name}/task/${id}`,
    method: 'get',
  })
}

export const RetryKwTask = (id) => {
  return request({
    url: `${api_name}/task/${id}/retry`,
    method: 'post',
  })
}

export const PickKwTask = (id, data) => {
  return request({
    url: `${api_name}/task/${id}/pick`,
    method: 'post',
    data,
  })
}

export const ExportKwTask = (id) => {
  return request({
    url: `${api_name}/task/${id}/export`,
    method: 'get',
    responseType: 'blob',
  })
}

// ============ 引擎配置 ============
export const GetKwConfig = () => {
  return request({
    url: `${api_name}/config`,
    method: 'get',
  })
}

export const SetKwConfig = (textProvider) => {
  return request({
    url: `${api_name}/config`,
    method: 'put',
    data: { textProvider },
  })
}
```

- [ ] **Step 2: src/router/modules/kw.js**

```javascript
const Layout = () => import('@/layout/index.vue')
const kwProduct = () => import('@/views/kw/product/index.vue')
const kwWordbank = () => import('@/views/kw/wordbank/index.vue')
const kwTask = () => import('@/views/kw/task/index.vue')

export default [
  {
    path: '/kw',
    component: Layout,
    name: 'kw',
    meta: {
      title: 'AI选词',
    },
    icon: 'Search',
    children: [
      {
        path: '/kwProduct',
        name: 'kwProduct',
        component: kwProduct,
        meta: {
          title: 'AI选词商品',
        },
      },
      {
        path: '/kwWordbank',
        name: 'kwWordbank',
        component: kwWordbank,
        meta: {
          title: 'AI选词词表',
        },
      },
      {
        path: '/kwTask',
        name: 'kwTask',
        component: kwTask,
        meta: {
          title: 'AI选词任务',
        },
      },
    ],
  },
]
```

- [ ] **Step 3: router/index.js 挂载**

仿照 `import mall from './modules/mall'` 加 `import kw from './modules/kw'`，并在 asyncRoutes 数组中加入 `kw`（先读 index.js 确认 asyncRoutes 聚合写法，与现有 mall/order 同位置同风格）。

- [ ] **Step 4: 验证（页面文件还不存在，先建空壳避免路由报错）**

```bash
mkdir -p /Users/qyk9527/webstormProject/spzx-admin/src/views/kw/{product,wordbank,task}
for d in product wordbank task; do
  cat > /Users/qyk9527/webstormProject/spzx-admin/src/views/kw/$d/index.vue <<EOF
<template>
  <div>建设中</div>
</template>
EOF
done
cd /Users/qyk9527/webstormProject/spzx-admin && npm run lint
```

Expected: lint 通过（无新增错误）。

- [ ] **Step 5: Commit**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin && git add src/api/kw.js src/router/modules/kw.js src/router/index.js src/views/kw && git commit -m "feat(kw): AI选词api与路由骨架"
```

---

### Task 11: 前端三页面

**Files:**
- Modify: `spzx-admin/src/views/kw/product/index.vue`（替换空壳）
- Modify: `spzx-admin/src/views/kw/wordbank/index.vue`（替换空壳）
- Modify: `spzx-admin/src/views/kw/task/index.vue`（替换空壳）

**Interfaces:**
- Consumes: `@/api/kw.js` 全部函数（Task 10）、ProTable 全局组件（无需 import）、Element Plus。
- Produces: 三页面完整功能。任务页顶部引擎开关读写 GetKwConfig/SetKwConfig。

- [ ] **Step 1: product/index.vue（商品选择 → 建任务）**

结构（Element Plus + ProTable，遵循 prettier 无分号单引号）：

```vue
<template>
  <div class="app-container">
    <el-card shadow="never">
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="query.keyword" placeholder="标题搜索" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="query.platformType" clearable style="width: 120px">
            <el-option label="淘宝" :value="1" />
            <el-option label="抖音" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">搜索</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="rows" v-loading="loading" border>
        <el-table-column label="图" width="90">
          <template #default="{ row }">
            <el-image v-if="row.imgUrl" :src="row.imgUrl" fit="cover"
              style="width: 60px; height: 60px" :preview-src-list="[row.imgUrl]" />
          </template>
        </el-table-column>
        <el-table-column prop="code" label="商品ID" width="140" />
        <el-table-column prop="title" label="标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="pricing" label="价格" width="100" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openCreate(row)">选词</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination layout="prev, pager, next, total" :total="total"
        :page-size="query.size" v-model:current-page="query.current"
        @current-change="load" style="margin-top: 12px" />
    </el-card>

    <el-dialog v-model="dlg" title="创建AI选词任务" width="480px">
      <el-form label-width="90px">
        <el-form-item label="商品">
          <span>{{ current.title }}</span>
        </el-form-item>
        <el-form-item label="词表批次">
          <el-select v-model="form.batchId" style="width: 100%">
            <el-option v-for="b in batches" :key="b.id"
              :label="`${b.name} (${b.wordCount}词)`" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="补充说明">
          <el-input v-model="form.note" type="textarea" :rows="3"
            placeholder="可选：材质/人群/风格等AI需知道的补充信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  GetKwProductPage,
  GetWordbankBatchList,
  CreateKwTask,
} from '@/api/kw'
import { useRouter } from 'vue-router'

const router = useRouter()
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ current: 1, size: 10, keyword: '', platformType: null })
const dlg = ref(false)
const current = ref({})
const batches = ref([])
const form = reactive({ batchId: null, note: '' })
const submitting = ref(false)

const load = async () => {
  loading.value = true
  try {
    const res = await GetKwProductPage(query.current, query.size, {
      keyword: query.keyword,
      platformType: query.platformType,
    })
    rows.value = res.data.records
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

const search = () => {
  query.current = 1
  load()
}

const openCreate = async (row) => {
  current.value = row
  const res = await GetWordbankBatchList()
  batches.value = res.data
  form.batchId = batches.value.length ? batches.value[0].id : null
  form.note = ''
  dlg.value = true
}

const submitCreate = async () => {
  if (!form.batchId) {
    ElMessage.warning('请先上传词表批次')
    return
  }
  submitting.value = true
  try {
    await CreateKwTask({ productId: current.value.id, batchId: form.batchId, note: form.note })
    ElMessage.success('任务已创建，正在后台运行')
    dlg.value = false
    router.push({ name: 'kwTask' })
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped></style>
```

- [ ] **Step 2: wordbank/index.vue（上传 + 批次 + 词条查看）**

结构与 product 页同款骨架：`el-upload`（drag multiple，auto-upload=false，手动收集 files 调 UploadWordbank）+ 批次 ProTable（name/wordCount/fileNames/createTime）+「查看词条」抽屉（el-drawer 内 el-table 分页调 GetWordbankItems，列：keyword/searchPopularity/clickRate/convRate/buyerCount/score）。上传成功后刷新批次列表并 ElMessage.success。样式 `<style lang="scss" scoped>`。

- [ ] **Step 3: task/index.vue（列表 + 详情 + 引擎开关）**

结构：

```vue
<template>
  <div class="app-container">
    <!-- 引擎开关 -->
    <el-card shadow="never" style="margin-bottom: 12px">
      <div style="display: flex; align-items: center; gap: 12px">
        <span>AI选词引擎：</span>
        <el-radio-group v-model="engine" @change="switchEngine">
          <el-radio-button v-for="p in providers.filter((x) => x.textModel)"
            :key="p.name" :value="p.name" :disabled="!p.hasKey">
            {{ p.name }}{{ p.hasKey ? '' : '（未配置key）' }}
          </el-radio-button>
        </el-radio-group>
        <span style="color: #999; font-size: 12px">
          下班/周末切官方峰谷价跑批量省钱
        </span>
      </div>
    </el-card>

    <!-- 任务列表 -->
    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading" border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="productCode" label="商品" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.status === 3" type="success">完成</el-tag>
            <el-tag v-else-if="row.status === 4" type="danger">失败</el-tag>
            <el-tag v-else-if="row.status === 0">待跑</el-tag>
            <el-tag v-else type="warning">{{ row.status === 1 ? '识品中' : '选词中' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="textProvider" label="引擎" width="130" />
        <el-table-column prop="createTime" label="创建时间" width="170" />
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 4" type="warning" size="small"
              @click="retry(row)">重试</el-button>
            <el-button v-if="row.status === 3" type="success" size="small"
              @click="exportTask(row)">导出</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情抽屉：profile 摘要 + 词表格(勾选) + 标题卡片 -->
    <el-drawer v-model="detailDlg" size="70%" title="任务详情">
      <!-- profile：category/material/audience/style/season 简要展示 -->
      <!-- 词表格：el-table selection 列 + match_score + bank_score + reason，
           勾选变化 debounce 调 PickKwTask(id, {wordIds}) -->
      <!-- 标题：el-card 列表 + reason -->
    </el-drawer>
  </div>
</template>
```

行为要求：
- onMounted 调 GetKwConfig 填 engine/providers；任务列表 3s 轮询（setInterval，存在 detailDlg 打开时也继续），任务全为终态(3/4)时降频到 10s。
- 详情打开起 GetKwTaskDetail；词表格用 `@selection-change` 收集 wordIds，变化后 800ms debounce 调 PickKwTask。
- exportTask 用 `ExportKwTask`（blob）→ `URL.createObjectURL` 下载 `kw_task_${id}.xlsx`。
- retry 调 RetryKwTask 后刷新列表。

- [ ] **Step 4: lint + 手动验证**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin && npm run lint
```

Expected: 无新增错误。然后 `npm run dev`（8501 需在线），浏览器 http://127.0.0.1:3001 登录 → 侧边栏出现「AI选词」三入口（sys_menu 已在 Task 1 入库；若菜单不显示，用 admin 账号登出重登刷新菜单缓存）→ 手动过：选商品→建任务→任务页看状态流转→详情勾词→导出。

- [ ] **Step 5: Commit**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin && git add src/views/kw && git commit -m "feat(kw): AI选词三页面(商品/词表/任务+引擎开关)"
```

---

### Task 12: 端到端验收（真实数据）

**Files:** 无新文件（验收任务）。

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 按设计文档第 11 节验收标准的验证记录。

- [ ] **Step 1: 真实词表验收**

用户提供生意参谋真实导出 Excel（搜索排行 Top300）。上传后：

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e \
  "SELECT COUNT(*), MIN(search_popularity) FROM kw_wordbank_item WHERE batch_id=<新batchId>"
```

验收点：解析列名映射正确（人气/点击率/转化率/买家数都有值）；去重生效；人气<60 已剔除；score 降序人工抽查 5 词合理。若真实导出表头与映射规则对不上（如「搜索人气」叫别的名字），**修 `mapColumns()` 的关键字映射并补该表头样例注释**，重传验证。

- [ ] **Step 2: 真实商品全流程**

选一个真实在售商品（建议睡衣类），建任务（带补充说明）。验收点（设计文档第 11 节）：
1. profile JSON 各字段合理（对照商品图人工核）
2. 匹配词理由是人话、高分词确实契合、排除维度词（如"儿童"）零混入
3. 3 个标题 ≤30 汉字、含高分词、无违禁词
4. 勾选 + 导出 xlsx 打开正常

- [ ] **Step 3: 引擎切换验收**

```bash
TOKEN="<登录token>"
curl -s -X PUT "http://127.0.0.1:8501/admin/kw/config" -H "token: $TOKEN" \
  -H "Content-Type: application/json" -d '{"textProvider":"deepseek"}'
```

验收点：deepseek key 未配时被拒；用户配好官方 key 后（改 application-local.yml 重启）切换成功、再跑一任务走官方（kw_select_task.text_provider=deepseek）。测完切回 tokens-store。

- [ ] **Step 4: 最终提交**

两仓库各打一个收尾 commit（如有零散改动），确认 `git status` 干净；向用户汇报验收结果与剩余事项（如 DeepSeek 官方 key 待用户开通后填入）。

---

## Self-Review 记录

- **Spec 覆盖**：spec 第 3 节流程（Task 6/7/8/11）、第 4 节 6 表（Task 1/4，另加 kw_config 第 7 表）、第 5 节评分（Task 5）、第 6 节 Provider 抽象+识品+选词+标题（Task 2/3/7）、第 7 节 11 接口（Task 6/8/9 全覆盖）、第 8 节前端（Task 10/11）、第 9 节配置（Task 2）、第 10 节风险（Excel 列名→Task 12 校准；JSON 失败→Task 3 重试；Top2000+分批→Task 7；product_media→已核实 file_type=1；异步轮询→Task 7/11；中转偶发超时→Task 3 重试+180s；key 未配拒切→Task 8）✅
- **已知妥协**：Result 错误构造的链式 API 需按实际类微调（已在 Task 8 标注）；标题勾选用 reason 前缀或加 picked 列二选一（推荐加列，已在 Task 7 标注）；Task 11 的 wordbank/task 页面给的是结构+行为要求而非逐行代码（组件为标准 Element Plus 模式，行为契约已完整列出）。
- **类型一致性**：`getProvider(key)`/`KEY_TEXT`/`KEY_VISION`（Task 3→7/8）、`upload(files,name,platformType)→Long`（Task 5→6）、`detail/retry/pickWords/pickTitles`（Task 7→8）、路由 name 三兄弟（Task 1 SQL→Task 10 路由）已交叉核对 ✅
