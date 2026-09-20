# 大模型 Provider 配置页面化（kw 引擎配置）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** provider 定义（base-url/api-key/模型/max_tokens/extra_body）从 yml 搬进 `kw_provider` 表 + yml 自动播种，后台新增「AI引擎配置」页面，增删改/停用/连通测试/文本+视觉双引擎切换全部页面操作即时生效，不再改 yml、不再重启。

**Architecture:** 新表 `kw_provider` 存 provider 定义（name 唯一标识）；`kw_config` 职责不变只存当前主用引擎两个键。`KwAiClient` 每次调用现读 DB（`KwProviderService.requireActive`），无缓存零失效。启动时表空且 yml `kw.providers` 非空则自动播种（之后 yml 该节作废）。

**Tech Stack:** Spring Boot 3.3.5 + Java 21 + MyBatis-Plus 3.5.9（纯 BaseMapper 无 XML）+ hutool JSON/HTTP；前端 Vue 3 `<script setup>` + Element Plus（手动全量导入）+ axios request util。

**Spec:** `docs/superpowers/specs/2026-09-20-llm-provider-config-design.md`

## Global Constraints

- 本项目**无测试套件**（AGENTS.md 明令勿跑 `mvn test`，前端无 test script）——每个任务的"验证"= 后端 `mvn compile` / 前端 `npm run lint` + `npm run build` + SQL 查询核对，不写单元测试。
- **不执行 git commit**（项目规则：仅用户明确要求时才提交）。
- mvn 不在 PATH，必须先 `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`；spzx-model 改动后需 `mvn install -pl spzx-model -DskipTests -q` 再编译 spzx-manager。
- 已知预存编译错误（与本次无关，忽略）：AbstractWechatPayStrategy:49 / PaypalOrderStrategy:45 / StripeCardStrategy:46。
- 业务错误返回模式：`Result.build(null, 204, "消息")`（204=DATA_ERROR）；成功 `Result.build(data)` / `Result.build(null)`。
- 前端 Prettier：单引号、无分号、printWidth 80；Element Plus 组件/图标全局注册，但 `ElMessage`/`ElMessageBox` 需显式 import；视图样式 `<style lang="scss" scoped>`。
- 前端动态菜单：路由 `name` 必须与 `sys_menu.component` 一致才会被保留（`src/pinia/modules/menu.js` 过滤）。
- MySQL CLI：`/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx`。
- **api-key 等凭据严禁出现在计划/代码/提交内容之外的任何输出中**；application-local.yml 是 gitignored。
- 菜单 id=68 当前空闲（sys_menu MAX(id)=67），admin 角色 role_id=9。

---

### Task 1: DDL + 菜单（kw_init.sql 追加并手动执行）

**Files:**
- Modify: `spzx-manager/src/main/resources/sql/kw_init.sql`（文件末尾追加）

**Interfaces:**
- Produces: 表 `kw_provider`（列见下）；菜单行 id=68 component=`kwConfig`；role 9 授权。后续所有后端任务依赖此表结构。

- [ ] **Step 1: 在 kw_init.sql 末尾追加 DDL 与菜单**

```sql

-- ============ 2026-09-20 provider 定义入库（spec: docs/superpowers/specs/2026-09-20-llm-provider-config-design.md）============

CREATE TABLE IF NOT EXISTS kw_provider (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL COMMENT '唯一标识，创建后不可改（任务快照按 name 引用）',
  base_url VARCHAR(200) NOT NULL,
  api_key VARCHAR(500) NOT NULL DEFAULT '' COMMENT '明文本地存储，与原yml等级一致，不入git',
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
) COMMENT 'AI provider 定义（运行时配置源）';

-- 菜单：运营管理(38)下，AI选词三页面(65-67)之后；写死 id=68（当前空闲）
INSERT INTO sys_menu (id, parent_id, title, component, sort_value, status)
SELECT 68, 38, 'AI引擎配置', 'kwConfig', 63, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_menu WHERE component = 'kwConfig');

-- 授权 admin 角色(role_id=9)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 9, 68
WHERE NOT EXISTS (SELECT 1 FROM sys_role_menu WHERE role_id = 9 AND menu_id = 68);
```

（整文件可重复执行：`CREATE TABLE IF NOT EXISTS` + `WHERE NOT EXISTS` 幂等；`INSERT IGNORE INTO kw_config` 对已有行是 no-op，不会覆盖用户已切换的引擎值。）

- [ ] **Step 2: 手动执行整个 kw_init.sql**

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx < /Users/qyk9527/ideaProject/spzx-parent/spzx-manager/src/main/resources/sql/kw_init.sql
```

- [ ] **Step 3: 验证**

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SHOW TABLES LIKE 'kw_provider'; SELECT id,parent_id,title,component,sort_value,status FROM sys_menu WHERE id=68; SELECT * FROM sys_role_menu WHERE role_id=9 AND menu_id=68;"
```

Expected: `kw_provider` 表存在；menu 行 (68,38,AI引擎配置,kwConfig,63,1)；role_menu 行 (9,68)。
另核对 `kw_config` 两行值未被改动（应仍为 tokens-store/tokens-store）：

```bash
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SELECT * FROM kw_config;"
```

---

### Task 2: 实体 + Mapper

**Files:**
- Create: `spzx-model/src/main/java/com/joker/spzx/model/entity/kw/KwProvider.java`
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/mapper/KwProviderMapper.java`

**Interfaces:**
- Produces: `KwProvider` 实体（字段名=驼峰列名：id/name/baseUrl/apiKey/visionModel/textModel/imageModel/maxTokens/extraBody/status/remark/createTime/updateTime，id 为 `Long`、status/maxTokens 为 `Integer`、时间为 `LocalDateTime`）；`KwProviderMapper extends BaseMapper<KwProvider>`。Task 3-6 依赖。

- [ ] **Step 1: 创建 KwProvider 实体**（仿 KwSelectTask 的 `IdType.AUTO` 模式）

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
@TableName("kw_provider")
public class KwProvider extends Model<KwProvider> {

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("name")
    private String name;

    @TableField("base_url")
    private String baseUrl;

    @TableField("api_key")
    private String apiKey;

    @TableField("vision_model")
    private String visionModel;

    @TableField("text_model")
    private String textModel;

    @TableField("image_model")
    private String imageModel;

    @TableField("max_tokens")
    private Integer maxTokens;

    @TableField("extra_body")
    private String extraBody;

    @TableField("status")
    private Integer status;

    @TableField("remark")
    private String remark;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
```

- [ ] **Step 2: 创建 KwProviderMapper**（仿 KwConfigMapper）

```java
package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.kw.KwProvider;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface KwProviderMapper extends BaseMapper<KwProvider> {
}
```

- [ ] **Step 3: 编译验证**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am
```

Expected: BUILD SUCCESS（3 个已知预存支付策略编译错误如出现则与本次无关——实际上 `mvn compile` 若因它们失败，以 `mvn compile -pl spzx-manager` 输出中**无 KwProvider 相关报错**为准）。

---

### Task 3: KwProviderService（运行时配置源 + 启动播种）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwProviderService.java`

**Interfaces:**
- Consumes: `KwProviderMapper`（Task 2）、`KwProperties.Provider`（现有，含 getBaseUrl/getApiKey/getVisionModel/getTextModel/getMaxTokens/getExtraBody）
- Produces:
  - `record ProviderDef(String name, String baseUrl, String apiKey, String visionModel, String textModel, Integer maxTokens, Map<String,Object> extraBody)` + `String modelFor(String kind)`
  - `ProviderDef get(String name)`（不存在返回 null）
  - `ProviderDef requireActive(String name, String kind)`（校验失败抛 RuntimeException，报错文案沿用 KwAiClient 语义）
  - `KwProvider getEntity(String name)`
  - `List<KwProvider> listAll()`
  - `ProviderDef toDef(KwProvider row)`（extra_body 反序列化）
  - `@PostConstruct seed()`（播种）

- [ ] **Step 1: 创建 KwProviderService**

```java
package com.joker.spzx.manager.service.kw;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.mapper.KwProviderMapper;
import com.joker.spzx.model.entity.kw.KwProvider;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwProviderService {

    @Autowired
    private KwProviderMapper kwProviderMapper;

    @Autowired
    private KwProperties props;

    /**
     * 运行时 provider 定义。KwAiClient 每次调用现读 DB，无缓存——
     * 本地 MySQL 单查 ~1ms 对比 LLM 秒级调用可忽略，页面改动即时生效。
     */
    public record ProviderDef(
            String name, String baseUrl, String apiKey,
            String visionModel, String textModel,
            Integer maxTokens, Map<String, Object> extraBody) {

        public String modelFor(String kind) {
            return "vision".equals(kind) ? visionModel : textModel;
        }
    }

    /** 启动播种：表空且 yml kw.providers 非空 → 按 yml 现值插入；表不存在仅 warn 跳过不阻塞启动 */
    @PostConstruct
    public void seed() {
        try {
            Long count = kwProviderMapper.selectCount(null);
            if (count != null && count > 0) {
                return;
            }
            if (props.getProviders().isEmpty()) {
                return;
            }
            for (Map.Entry<String, KwProperties.Provider> e : props.getProviders().entrySet()) {
                KwProperties.Provider p = e.getValue();
                KwProvider row = new KwProvider();
                row.setName(e.getKey());
                row.setBaseUrl(p.getBaseUrl());
                row.setApiKey(p.getApiKey() == null ? "" : p.getApiKey());
                row.setVisionModel(p.getVisionModel());
                row.setTextModel(p.getTextModel());
                row.setMaxTokens(p.getMaxTokens());
                row.setExtraBody(p.getExtraBody() == null || p.getExtraBody().isEmpty()
                        ? null : JSONUtil.toJsonStr(p.getExtraBody()));
                row.setStatus(1);
                row.setRemark("从yml自动播种");
                kwProviderMapper.insert(row);
            }
            log.info("已从 yml 播种 {} 个 provider 到 kw_provider 表", props.getProviders().size());
        } catch (Exception e) {
            log.warn("kw_provider 播种跳过（表可能未创建）: {}", e.getMessage());
        }
    }

    public KwProvider getEntity(String name) {
        return kwProviderMapper.selectOne(new LambdaQueryWrapper<KwProvider>()
                .eq(KwProvider::getName, name).last("limit 1"));
    }

    public ProviderDef get(String name) {
        KwProvider row = getEntity(name);
        return row == null ? null : toDef(row);
    }

    /** 校验存在 + 启用 + 有 key + kind 对应模型已配，不满足抛 RuntimeException（沿用 KwAiClient 报错语义） */
    public ProviderDef requireActive(String name, String kind) {
        KwProvider row = getEntity(name);
        if (row == null || row.getBaseUrl() == null || row.getBaseUrl().isBlank()) {
            throw new RuntimeException("AI provider 未配置: " + name);
        }
        if (row.getStatus() == null || row.getStatus() != 1) {
            throw new RuntimeException("AI provider 已停用: " + name);
        }
        if (row.getApiKey() == null || row.getApiKey().isBlank()) {
            throw new RuntimeException("AI provider 未配置 key: " + name);
        }
        String model = row.modelFor(kind);
        if (model == null || model.isBlank()) {
            throw new RuntimeException("provider " + name + " 未配置 " + kind + " 模型");
        }
        return toDef(row);
    }

    public List<KwProvider> listAll() {
        return kwProviderMapper.selectList(new LambdaQueryWrapper<KwProvider>()
                .orderByAsc(KwProvider::getId));
    }

    public ProviderDef toDef(KwProvider row) {
        Map<String, Object> extra = null;
        if (row.getExtraBody() != null && !row.getExtraBody().isBlank()) {
            try {
                extra = JSONUtil.parseObj(row.getExtraBody());
            } catch (Exception e) {
                log.warn("provider {} extra_body 非法JSON，忽略: {}", row.getName(), e.getMessage());
            }
        }
        return new ProviderDef(row.getName(), row.getBaseUrl(), row.getApiKey(),
                row.getVisionModel(), row.getTextModel(), row.getMaxTokens(), extra);
    }
}
```

注：`requireActive` 里 `row.modelFor(kind)` 是实体方法——在 Task 2 实体中补一个便捷方法（或此处改为内联三目 `"vision".equals(kind) ? row.getVisionModel() : row.getTextModel()`，**实施者按后者内联**，实体保持纯数据类，避免 model 包混入逻辑）。

- [ ] **Step 2: 编译验证**（同 Task 2 Step 3）

---

### Task 4: KwAiClient 改为现读 DB + KwProperties 注释

**Files:**
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/service/kw/KwAiClient.java`（call 方法 + 依赖注入）
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/config/KwProperties.java:14`（providers 字段注释）

**Interfaces:**
- Consumes: `KwProviderService.requireActive(name, kind)` → `ProviderDef`（Task 3）
- Produces: 对外方法签名不变（`text(providerName, prompt)` / `vision(providerName, contentParts)`），调用方 `KwTaskService` 零改动。

- [ ] **Step 1: 改造 KwAiClient**

1. 字段注入区新增（保留 props——timeout 仍走 yml；kwConfigService 原样保留）：

```java
    @Autowired
    private KwProviderService kwProviderService;
```

2. `call()` 开头整段替换：

```java
    private String call(String providerName, String kind, JSONArray messages) {
        KwProviderService.ProviderDef p = kwProviderService.requireActive(providerName, kind);
        String model = p.modelFor(kind);
        RuntimeException last = null;
```

（删除原 `KwProperties.Provider p = props.getProviders().get(providerName); ...` 的 null/模型校验 6 行。）

3. 循环体内 record 访问器替换（record 无 getter 风格方法）：

- `body.set("max_tokens", p.getMaxTokens() != null ? p.getMaxTokens() : 4096);` → `body.set("max_tokens", p.maxTokens() != null ? p.maxTokens() : 4096);`
- `if (p.getExtraBody() != null) { p.getExtraBody().forEach(body::set); }` → `if (p.extraBody() != null) { p.extraBody().forEach(body::set); }`
- `HttpRequest.post(p.getBaseUrl() + "/chat/completions")` → `HttpRequest.post(p.baseUrl() + "/chat/completions")`
- `.header("Authorization", "Bearer " + p.getApiKey())` → `.header("Authorization", "Bearer " + p.apiKey())`

其余（2 次重试、temperature 0.3、错误解析、stripFence、日志文案）全部不动。

- [ ] **Step 2: KwProperties providers 字段加注释**

```java
    /** providers 仅用于首次播种 kw_provider 表（表空时）；运行时配置读 DB，改 yml 此节不再生效 */
    private Map<String, Provider> providers = new LinkedHashMap<>();
```

- [ ] **Step 3: 编译验证**（同 Task 2 Step 3，无需重新 install spzx-model）

---

### Task 5: KwProviderController（CRUD/状态/删除/连通测试）

**Files:**
- Create: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwProviderController.java`

**Interfaces:**
- Consumes: `KwProviderMapper`、`KwProviderService`（getEntity/listAll）、`KwConfigService.getProvider(KEY_TEXT/KEY_VISION)`（判断主用）、hutool HttpRequest/JSONUtil
- Produces: REST 端点（见步骤）；前端 Task 7 依赖。

- [ ] **Step 1: 创建 KwProviderController**

```java
package com.joker.spzx.manager.controller;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.mapper.KwProviderMapper;
import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.manager.service.kw.KwProviderService;
import com.joker.spzx.model.entity.kw.KwProvider;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/provider")
public class KwProviderController {

    @Autowired
    private KwProviderMapper kwProviderMapper;

    @Autowired
    private KwProviderService kwProviderService;

    @Autowired
    private KwConfigService kwConfigService;

    /** name 唯一标识；编辑时 name 不可改；apiKey 为空/缺失 = 保留原值 */
    public record SaveDto(String name, String baseUrl, String apiKey,
                          String visionModel, String textModel, String imageModel,
                          Integer maxTokens, String extraBody, String remark) {
    }

    /** 全量列表；apiKey 不回传，只回 hasKey + keyTail(尾4位) */
    @GetMapping("/list")
    public Result<List<Map<String, Object>>> list() {
        List<Map<String, Object>> out = new ArrayList<>();
        for (KwProvider row : kwProviderService.listAll()) {
            out.add(toMap(row));
        }
        return Result.build(out);
    }

    @PostMapping
    public Result<Void> save(@RequestBody SaveDto dto) {
        if (dto.name() == null || dto.name().isBlank()) {
            return Result.build(null, 204, "name 不能为空");
        }
        if (dto.baseUrl() == null || dto.baseUrl().isBlank()) {
            return Result.build(null, 204, "base_url 不能为空");
        }
        if (kwProviderService.getEntity(dto.name().trim()) != null) {
            return Result.build(null, 204, "name 已存在: " + dto.name());
        }
        String extraErr = extraBodyError(dto.extraBody());
        if (extraErr != null) {
            return Result.build(null, 204, extraErr);
        }
        KwProvider row = new KwProvider();
        applyDto(row, dto, null);
        row.setStatus(1);
        kwProviderMapper.insert(row);
        return Result.build(null);
    }

    @PutMapping
    public Result<Void> update(@RequestBody SaveDto dto) {
        if (dto.name() == null || dto.name().isBlank()) {
            return Result.build(null, 204, "name 不能为空");
        }
        KwProvider row = kwProviderService.getEntity(dto.name());
        if (row == null) {
            return Result.build(null, 204, "provider 不存在: " + dto.name());
        }
        String extraErr = extraBodyError(dto.extraBody());
        if (extraErr != null) {
            return Result.build(null, 204, extraErr);
        }
        applyDto(row, dto, row.getApiKey());
        kwProviderMapper.updateById(row);
        return Result.build(null);
    }

    @PutMapping("/status/{id}/{status}")
    public Result<Void> status(@PathVariable Long id, @PathVariable Integer status) {
        if (status == null || (status != 0 && status != 1)) {
            return Result.build(null, 204, "status 只能是 0 或 1");
        }
        KwProvider row = kwProviderMapper.selectById(id);
        if (row == null) {
            return Result.build(null, 204, "provider 不存在");
        }
        if (status == 0) {
            String err = mainEngineGuard(row.getName(), "停用");
            if (err != null) {
                return Result.build(null, 204, err);
            }
        }
        row.setStatus(status);
        kwProviderMapper.updateById(row);
        return Result.build(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        KwProvider row = kwProviderMapper.selectById(id);
        if (row == null) {
            return Result.build(null, 204, "provider 不存在");
        }
        String err = mainEngineGuard(row.getName(), "删除");
        if (err != null) {
            return Result.build(null, 204, err);
        }
        kwProviderMapper.deleteById(id);
        return Result.build(null);
    }

    /** 连通测试：优先 textModel、无则 visionModel，都无→报错；max_tokens=16 单轮 ping；返回 {ok, costMs, error}，不落库 */
    @PostMapping("/test/{id}")
    public Result<Map<String, Object>> test(@PathVariable Long id) {
        KwProvider row = kwProviderMapper.selectById(id);
        if (row == null) {
            return Result.build(null, 204, "provider 不存在");
        }
        Map<String, Object> out = new LinkedHashMap<>();
        String model = row.getTextModel() != null && !row.getTextModel().isBlank()
                ? row.getTextModel() : row.getVisionModel();
        if (row.getBaseUrl() == null || row.getBaseUrl().isBlank()
                || row.getApiKey() == null || row.getApiKey().isBlank() || model == null || model.isBlank()) {
            out.put("ok", false);
            out.put("error", "base_url / api_key / text或vision模型 未配全，无法测试");
            return Result.build(out);
        }
        JSONObject body = new JSONObject();
        body.set("model", model);
        JSONArray messages = new JSONArray();
        JSONObject msg = new JSONObject();
        msg.set("role", "user");
        msg.set("content", "ping");
        messages.add(msg);
        body.set("messages", messages);
        body.set("max_tokens", 16);
        if (row.getExtraBody() != null && !row.getExtraBody().isBlank()) {
            try {
                JSONUtil.parseObj(row.getExtraBody()).forEach(body::set);
            } catch (Exception ignored) {
            }
        }
        long start = System.currentTimeMillis();
        try {
            String resp = HttpRequest.post(row.getBaseUrl() + "/chat/completions")
                    .header("Authorization", "Bearer " + row.getApiKey())
                    .header("Content-Type", "application/json")
                    .body(body.toString())
                    .timeout(60000)
                    .execute()
                    .body();
            long costMs = System.currentTimeMillis() - start;
            JSONObject respJson = JSONUtil.parseObj(resp);
            if (respJson.containsKey("error")) {
                out.put("ok", false);
                out.put("costMs", costMs);
                out.put("error", respJson.getJSONObject("error").getStr("message", ""));
            } else if (respJson.containsKey("choices")) {
                out.put("ok", true);
                out.put("costMs", costMs);
                out.put("error", "");
            } else {
                out.put("ok", false);
                out.put("costMs", costMs);
                out.put("error", "响应无 choices: " + resp);
            }
        } catch (Exception e) {
            out.put("ok", false);
            out.put("costMs", System.currentTimeMillis() - start);
            out.put("error", e.getMessage());
        }
        return Result.build(out);
    }

    /** 当前主用（text/vision 任一命中）→ 返回拒绝消息，否则 null */
    private String mainEngineGuard(String name, String action) {
        if (name.equals(kwConfigService.getProvider(KwConfigService.KEY_TEXT))) {
            return "「" + name + "」是当前文本主用引擎，请先切换后再" + action;
        }
        if (name.equals(kwConfigService.getProvider(KwConfigService.KEY_VISION))) {
            return "「" + name + "」是当前视觉主用引擎，请先切换后再" + action;
        }
        return null;
    }

    /** name 不可改（按 name 定位行后仅更新可变字段）；apiKey 空 = 保留原值 */
    private void applyDto(KwProvider row, SaveDto dto, String oldKey) {
        row.setName(dto.name().trim());
        row.setBaseUrl(dto.baseUrl().trim());
        String key = dto.apiKey() == null || dto.apiKey().isBlank() ? oldKey : dto.apiKey().trim();
        row.setApiKey(key == null ? "" : key);
        row.setVisionModel(blankToNull(dto.visionModel()));
        row.setTextModel(blankToNull(dto.textModel()));
        row.setImageModel(blankToNull(dto.imageModel()));
        row.setMaxTokens(dto.maxTokens());
        row.setExtraBody(dto.extraBody() == null || dto.extraBody().isBlank()
                ? null : dto.extraBody().trim());
        row.setRemark(dto.remark());
    }

    private String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }

    /** 非空时必须是合法 JSON 对象，否则返回错误消息 */
    private String extraBodyError(String extraBody) {
        if (extraBody == null || extraBody.isBlank()) {
            return null;
        }
        try {
            JSONUtil.parseObj(extraBody);
            return null;
        } catch (Exception e) {
            return "extra_body 必须是合法 JSON 对象，如 {\"thinking\":{\"type\":\"disabled\"}}";
        }
    }

    private Map<String, Object> toMap(KwProvider row) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("id", row.getId());
        p.put("name", row.getName());
        p.put("baseUrl", row.getBaseUrl());
        p.put("visionModel", row.getVisionModel());
        p.put("textModel", row.getTextModel());
        p.put("imageModel", row.getImageModel());
        p.put("maxTokens", row.getMaxTokens());
        boolean hasKey = row.getApiKey() != null && !row.getApiKey().isBlank();
        p.put("hasKey", hasKey);
        p.put("keyTail", hasKey
                ? row.getApiKey().substring(Math.max(0, row.getApiKey().length() - 4)) : "");
        p.put("status", row.getStatus());
        p.put("remark", row.getRemark());
        p.put("updateTime", row.getUpdateTime());
        return p;
    }
}
```

- [ ] **Step 2: 编译验证**（同 Task 2 Step 3）

---

### Task 6: KwConfigController 扩展（双引擎 GET/PUT，provider 来源改 DB）

**Files:**
- Modify: `spzx-manager/src/main/java/com/joker/spzx/manager/controller/KwConfigController.java`（整文件重写如下）

**Interfaces:**
- Consumes: `KwProviderService.getEntity/listAll`（Task 3）、`KwConfigService`
- Produces: GET `/admin/kw/config` 返回 `{textProvider, visionProvider, providers:[{name,hasKey,keyTail,visionModel,textModel,status}]}`；PUT body `{textProvider?, visionProvider?}` 传了才改。兼容老前端 task 页（它只发 textProvider、读 name/hasKey/textModel 字段）。

- [ ] **Step 1: 重写 KwConfigController**

```java
package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.kw.KwConfigService;
import com.joker.spzx.manager.service.kw.KwProviderService;
import com.joker.spzx.model.entity.kw.KwProvider;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/config")
public class KwConfigController {

    @Autowired
    private KwConfigService kwConfigService;

    @Autowired
    private KwProviderService kwProviderService;

    /** 两个键均可选；传了才改（老前端只传 textProvider，兼容） */
    public record SetDto(String textProvider, String visionProvider) {
    }

    @GetMapping
    public Result<Map<String, Object>> get() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("textProvider", kwConfigService.getProvider(KwConfigService.KEY_TEXT));
        out.put("visionProvider", kwConfigService.getProvider(KwConfigService.KEY_VISION));
        List<Map<String, Object>> providers = new ArrayList<>();
        for (KwProvider row : kwProviderService.listAll()) {
            Map<String, Object> p = new LinkedHashMap<>();
            p.put("name", row.getName());
            boolean hasKey = row.getApiKey() != null && !row.getApiKey().isBlank();
            p.put("hasKey", hasKey);
            p.put("keyTail", hasKey
                    ? row.getApiKey().substring(Math.max(0, row.getApiKey().length() - 4)) : "");
            p.put("visionModel", row.getVisionModel());
            p.put("textModel", row.getTextModel());
            p.put("status", row.getStatus());
            providers.add(p);
        }
        out.put("providers", providers);
        return Result.build(out);
    }

    @PutMapping
    public Result<Void> set(@RequestBody SetDto dto) {
        if (dto.textProvider() != null) {
            String err = validateForSwitch(dto.textProvider());
            if (err != null) {
                return Result.build(null, 204, err);
            }
            kwConfigService.setProvider(KwConfigService.KEY_TEXT, dto.textProvider());
        }
        if (dto.visionProvider() != null) {
            String err = validateForSwitch(dto.visionProvider());
            if (err != null) {
                return Result.build(null, 204, err);
            }
            kwConfigService.setProvider(KwConfigService.KEY_VISION, dto.visionProvider());
        }
        return Result.build(null);
    }

    /** 切换校验：存在 + 启用 + 有 key */
    private String validateForSwitch(String name) {
        KwProvider row = kwProviderService.getEntity(name);
        if (row == null) {
            return "provider 不存在: " + name;
        }
        if (row.getStatus() == null || row.getStatus() != 1) {
            return "provider 已停用: " + name;
        }
        if (row.getApiKey() == null || row.getApiKey().isBlank()) {
            return "provider 未配置 key: " + name;
        }
        return null;
    }
}
```

- [ ] **Step 2: 编译验证**（同 Task 2 Step 3）

---

### Task 7: 前端（api + 路由 + AI引擎配置页面 + task 页兼容修改）

**Files:**
- Modify: `webstormProject/spzx-admin/src/api/kw.js`（文件末尾追加 + SetKwConfig 改签名）
- Modify: `webstormProject/spzx-admin/src/router/modules/kw.js`（加路由）
- Create: `webstormProject/spzx-admin/src/views/kw/config/index.vue`
- Modify: `webstormProject/spzx-admin/src/views/kw/task/index.vue:9` 与 `:234`（兼容修改）

**Interfaces:**
- Consumes: Task 5/6 的后端端点
- Produces: 页面路由 name=`kwConfig`（与 sys_menu.component='kwConfig' 对应）

- [ ] **Step 1: api/kw.js — SetKwConfig 改为对象参数（向后兼容端点）**

```javascript
export const SetKwConfig = data => {
  return request({
    url: `${api_name}/config`,
    method: 'put',
    data,
  })
}
```

（GetKwConfig 不动。规格书里的 GetKwEngineConfig/SwitchKwEngine 即这两个现有函数的扩展，不再新增别名，避免重复封装。）

- [ ] **Step 2: api/kw.js — 末尾追加 provider 接口**

```javascript

// ============ AI引擎配置（provider 定义入库） ============
export const GetKwProviderList = () => {
  return request({
    url: `${api_name}/provider/list`,
    method: 'get',
  })
}

// isEdit=true 走 PUT（按 name 定位更新，name 不可改），否则 POST 新增
export const SaveKwProvider = (data, isEdit) => {
  return request({
    url: api_name + '/provider',
    method: isEdit ? 'put' : 'post',
    data,
  })
}

export const UpdateKwProviderStatus = (id, status) => {
  return request({
    url: `${api_name}/provider/status/${id}/${status}`,
    method: 'put',
  })
}

export const DeleteKwProvider = id => {
  return request({
    url: `${api_name}/provider/${id}`,
    method: 'delete',
  })
}

export const TestKwProvider = id => {
  return request({
    url: `${api_name}/provider/test/${id}`,
    method: 'post',
  })
}
```

- [ ] **Step 3: router/modules/kw.js — 加路由**

文件顶部 import 区加：

```javascript
const kwConfig = () => import('@/views/kw/config/index.vue')
```

children 数组末尾（kwTask 之后）加：

```javascript
      {
        path: '/kwConfig',
        name: 'kwConfig',
        component: kwConfig,
        meta: {
          title: 'AI引擎配置',
        },
      },
```

- [ ] **Step 4: 创建 views/kw/config/index.vue**

```vue
<template>
  <div class="app-container">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="模型名与 provider 绑定；换 provider 后建议先跑一个小任务验证（thinking 类参数属模型家族，可能需调整 extra_body）"
      style="margin-bottom: 12px"
    />

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>当前文本引擎（选词/标题）</template>
          <el-select
            v-model="textEngine"
            style="width: 100%"
            @change="switchText"
          >
            <el-option
              v-for="p in enabledProviders"
              :key="p.name"
              :label="p.name + '（' + (p.textModel || '未配文本模型') + '）'"
              :value="p.name"
            />
          </el-select>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>当前视觉引擎（识品）</template>
          <el-select
            v-model="visionEngine"
            style="width: 100%"
            @change="switchVision"
          >
            <el-option
              v-for="p in enabledProviders"
              :key="p.name"
              :label="p.name + '（' + (p.visionModel || '未配视觉模型') + '）'"
              :value="p.name"
            />
          </el-select>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <div style="margin-bottom: 12px">
        <el-button type="primary" @click="openAdd">新增 Provider</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border>
        <el-table-column prop="name" label="名称" width="130" />
        <el-table-column
          prop="baseUrl"
          label="Base URL"
          min-width="200"
          show-overflow-tooltip
        />
        <el-table-column
          prop="textModel"
          label="文本模型"
          min-width="140"
          show-overflow-tooltip
        />
        <el-table-column
          prop="visionModel"
          label="视觉模型"
          min-width="140"
          show-overflow-tooltip
        />
        <el-table-column prop="maxTokens" label="max_tokens" width="100" />
        <el-table-column label="API Key" width="110">
          <template #default="{ row }">
            <span v-if="row.hasKey">••••{{ row.keyTail }}</span>
            <el-tag v-else type="danger" size="small">未配置</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="remark"
          label="备注"
          min-width="120"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openEdit(row)">
              编辑
            </el-button>
            <el-button
              size="small"
              :loading="testingId === row.id"
              @click="test(row)"
            >
              测试
            </el-button>
            <el-button
              size="small"
              :type="row.status === 1 ? 'warning' : 'success'"
              @click="toggle(row)"
            >
              {{ row.status === 1 ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" @click="remove(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dlg"
      :title="editName ? '编辑 Provider' : '新增 Provider'"
      width="560px"
    >
      <el-form label-width="110px">
        <el-form-item label="名称">
          <el-input
            v-model="form.name"
            :disabled="!!editName"
            placeholder="唯一标识，如 tokens-store"
          />
          <div v-if="editName" class="form-tip">
            创建后不可改，任务快照按 name 引用
          </div>
        </el-form-item>
        <el-form-item label="Base URL" required>
          <el-input v-model="form.baseUrl" placeholder="https://tokens.store/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="form.apiKey"
            type="password"
            show-password
            :placeholder="editName ? '留空则不修改' : 'sk-... / ek-...'"
          />
        </el-form-item>
        <el-form-item label="文本模型">
          <el-input v-model="form.textModel" placeholder="如 deepseek-v4-flash" />
        </el-form-item>
        <el-form-item label="视觉模型">
          <el-input
            v-model="form.visionModel"
            placeholder="识品用，须支持视觉，如 qwen3.8-max"
          />
        </el-form-item>
        <el-form-item label="生图模型">
          <el-input v-model="form.imageModel" placeholder="预留列，本期不使用" />
        </el-form-item>
        <el-form-item label="max_tokens">
          <el-input-number
            v-model="form.maxTokens"
            :min="256"
            :max="65536"
            :step="256"
          />
        </el-form-item>
        <el-form-item label="extra_body">
          <el-input
            v-model="form.extraBody"
            type="textarea"
            :rows="3"
            placeholder='JSON 对象，如 {"thinking":{"type":"disabled"}}'
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  GetKwProviderList,
  SaveKwProvider,
  UpdateKwProviderStatus,
  DeleteKwProvider,
  TestKwProvider,
  GetKwConfig,
  SetKwConfig,
} from '@/api/kw'

// ============ 列表 + 引擎状态 ============
const rows = ref([])
const loading = ref(false)
const textEngine = ref('')
const visionEngine = ref('')

const enabledProviders = computed(() => rows.value.filter(p => p.status === 1))

const load = async () => {
  loading.value = true
  try {
    const res = await GetKwProviderList()
    rows.value = res.data || []
  } finally {
    loading.value = false
  }
}

const loadConfig = async () => {
  const res = await GetKwConfig()
  textEngine.value = res.data.textProvider
  visionEngine.value = res.data.visionProvider
}

// ============ 引擎切换 ============
const switchText = async val => {
  if (!val) return
  const res = await SetKwConfig({ textProvider: val })
  if (res.code !== 200) {
    ElMessage.error(res.message || '切换失败')
    loadConfig()
    return
  }
  ElMessage.success('文本引擎已切换，即时生效，无需重启')
}

const switchVision = async val => {
  if (!val) return
  const res = await SetKwConfig({ visionProvider: val })
  if (res.code !== 200) {
    ElMessage.error(res.message || '切换失败')
    loadConfig()
    return
  }
  ElMessage.success('视觉引擎已切换，即时生效，无需重启')
}

// ============ 新增 / 编辑 ============
const dlg = ref(false)
const editName = ref('')
const saving = ref(false)
const emptyForm = () => ({
  name: '',
  baseUrl: '',
  apiKey: '',
  textModel: '',
  visionModel: '',
  imageModel: '',
  maxTokens: 4096,
  extraBody: '',
  remark: '',
})
const form = reactive(emptyForm())

const openAdd = () => {
  editName.value = ''
  Object.assign(form, emptyForm())
  dlg.value = true
}

const openEdit = row => {
  editName.value = row.name
  Object.assign(form, emptyForm(), {
    name: row.name,
    baseUrl: row.baseUrl,
    apiKey: '',
    textModel: row.textModel || '',
    visionModel: row.visionModel || '',
    imageModel: row.imageModel || '',
    maxTokens: row.maxTokens || 4096,
    extraBody: row.extraBody || '',
    remark: row.remark || '',
  })
  dlg.value = true
}

const save = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  if (!form.baseUrl.trim()) {
    ElMessage.warning('请填写 Base URL')
    return
  }
  if (form.extraBody && form.extraBody.trim()) {
    try {
      const o = JSON.parse(form.extraBody)
      if (!o || typeof o !== 'object' || Array.isArray(o)) throw new Error('not object')
    } catch {
      ElMessage.error(
        'extra_body 必须是合法 JSON 对象，如 {"thinking":{"type":"disabled"}}'
      )
      return
    }
  }
  saving.value = true
  try {
    const res = await SaveKwProvider(
      { ...form, extraBody: form.extraBody || '' },
      !!editName.value
    )
    if (res.code !== 200) {
      ElMessage.error(res.message || '保存失败')
      return
    }
    ElMessage.success('已保存，即时生效')
    dlg.value = false
    load()
  } finally {
    saving.value = false
  }
}

// ============ 测试 / 停用启用 / 删除 ============
const testingId = ref(null)

const test = async row => {
  testingId.value = row.id
  try {
    const res = await TestKwProvider(row.id)
    if (res.code !== 200) {
      ElMessage.error(res.message || '测试失败')
      return
    }
    if (res.data.ok) {
      ElMessage.success(`连通正常（${res.data.costMs}ms）`)
    } else {
      ElMessage.error(`测试失败：${res.data.error}（${res.data.costMs}ms）`)
    }
  } finally {
    testingId.value = null
  }
}

const toggle = async row => {
  const target = row.status === 1 ? 0 : 1
  const res = await UpdateKwProviderStatus(row.id, target)
  if (res.code !== 200) {
    ElMessage.error(res.message || '操作失败')
    return
  }
  ElMessage.success(target === 1 ? '已启用' : '已停用')
  load()
}

const remove = async row => {
  try {
    await ElMessageBox.confirm(
      `确认删除 provider「${row.name}」？在途任务若按该 name 引用，调用时会报 provider 不存在。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  const res = await DeleteKwProvider(row.id)
  if (res.code !== 200) {
    ElMessage.error(res.message || '删除失败')
    return
  }
  ElMessage.success('已删除')
  load()
}

onMounted(() => {
  load()
  loadConfig()
})
</script>

<style lang="scss" scoped>
.form-tip {
  color: #999;
  font-size: 12px;
  line-height: 1.4;
  margin-top: 4px;
}
</style>
```

注意：`openEdit` 里 `row.extraBody` —— 列表接口 toMap 未返回 extraBody，编辑弹窗 extra_body 显示为空属预期（留空不修改该字段语义不成立——extra_body 会被置 null）。**修正：toMap 需加 `p.put("extraBody", row.getExtraBody())`**（回 Task 5 的 toMap 中、`p.put("remark", ...)` 之前补一行；extraBody 非敏感可回显）。实施者确保两处一致。

- [ ] **Step 5: task/index.vue 兼容修改**

1. 行 9 `providers.filter(x => x.textModel)` → `providers.filter(x => x.textModel && x.status === 1)`（GET 现在返回 DB 行带 status，过滤停用项）。
2. 行 234 `await SetKwConfig(val)` → `await SetKwConfig({ textProvider: val })`（适配新签名）。

- [ ] **Step 6: 前端验证**

```bash
cd /Users/qyk9527/webstormProject/spzx-admin && npm run lint && npm run build
```

Expected: lint 0 error；build 成功。

---

### Task 8: 运行时验收（需重启 8501 后端）

**Files:** 无代码改动。前置：Task 1-7 全部完成。

- [ ] **Step 1: 打包并重启后端**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
cd /Users/qyk9527/ideaProject/spzx-parent && mvn package -pl spzx-manager -am -DskipTests -q
lsof -ti:8501 | xargs kill 2>/dev/null; sleep 2
nohup java -jar /Users/qyk9527/ideaProject/spzx-parent/spzx-manager/target/spzx-manager.jar > /tmp/spzx-manager.log 2>&1 &
```

（若 8501 是用户 IDEA 里跑的 spring-boot:run，先问用户再杀。）

- [ ] **Step 2: 验证播种 + 接口**

```bash
sleep 25
grep -E "已从 yml 播种|播种跳过" /tmp/spzx-manager.log
/usr/local/mysql/bin/mysql -uroot -proot123456 db_spzx -e "SELECT id,name,base_url,text_model,vision_model,max_tokens,extra_body,status,remark FROM kw_provider;"
```

Expected: 日志出现「已从 yml 播种 3 个 provider」；表里 3 行（tokens-store 有 key、模型/extra_body 与 yml 一致、status=1、remark=从yml自动播种）。

- [ ] **Step 3: 用户浏览器验收**（提示用户登录 3001 → 运营管理 → AI引擎配置）

对照 spec §8 验收 2-6：改 textModel 不重启即生效、新增 provider+测试连通+切换、视觉切换、停用主用被拒、非法 extra_body 被前端拦截。

- [ ] **Step 4: 凭据收口（验收通过后，需用户确认）**

确认页面/选词任务正常后，把 `spzx-manager/src/main/resources/application-local.yml` 的 `kw.providers` 下 3 个 `api-key` 值清为 `""`（结构保留作播种数据源；DB 已是唯一凭据来源）。此步**必须用户点头后才做**。

- [ ] **Step 5: AGENTS.md 更新**

`~/AGENTS.md` AI选词段落追加一句：provider 定义已入 `kw_provider` 表（后台「AI引擎配置」页面维护），`application-local.yml` 的 `kw.providers` 仅作首次播种、改 yml 不再生效；换引擎/改 key/改模型不再需要重启 8501。

---

## Self-Review 记录

1. **Spec 覆盖**：§4 DDL+菜单+播种（Task 1/3）、§5.1 service（Task 3）、§5.2 client 改造（Task 4）、§5.3 provider controller 6 端点（Task 5）、§5.4 config 扩展（Task 6）、§5.5 properties 去留（Task 4 Step 2）、§6 前端三件套+顶部提示语（Task 7）、§7 风险对策（主用守卫/二次确认/extra_body 校验/脱敏/收口均已入任务）、§8 验收（Task 8）。偏差 2 处已注明：api 函数复用 GetKwConfig/SetKwConfig 不加别名（Task 7 Step 1）；test 超时定 60s 固定值。
2. **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码。
3. **类型一致性**：ProviderDef 七字段与 KwAiClient 用法（maxTokens()/extraBody()/baseUrl()/apiKey()/modelFor(kind)）一致；requireActive 报错文案沿用原语义；SetDto{textProvider,visionProvider} 与 task 页 `{textProvider: val}` 及 config 页两种调用一致；前端 res.code/res.data 取值与 request.js 返回整包 Result 约定一致。已修正两处自查发现：requireActive 内联三目（实体不带逻辑）、toMap 补 extraBody 回显。
