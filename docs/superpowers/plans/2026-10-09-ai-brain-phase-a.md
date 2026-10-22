# AI Brain Phase A 核心 + 调参试打台（后端）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一个独立的 Java/Spring AI 服务（`spzx-ai-brain`），提供可调参、完全沙盒隔离的 `AI Brain` 内核与 `/console/*` 试打 API。

**Architecture:** 独立 Spring Boot 3.4.5 工程，Spring AI 1.0.x 调 OpenAI 兼容模型；Provider 凭据与运行配置存 MySQL（`db_ai_brain`）；所有业务能力走 canonical 输入输出；试打路径用独立沙盒表 + 出站短路，物理上无法外发。核心逻辑与 Spring/网络解耦，用纯 JUnit 可测。

**Tech Stack:** Java 21、Spring Boot 3.4.5、Spring AI 1.0.0（`spring-ai-openai` core，手动构建模型，不用 starter 自动装配）、MyBatis-Plus 3.5.9、MySQL 8、JUnit 5、Maven（IDEA 内置）。

## Global Constraints

- **不执行任何 git 提交**（用户明确）。所有改动只写盘。
- 工程目录：`/Users/qyk9527/ideaProject/spzx-ai-brain`（`spzx-parent` 的**兄弟目录**，独立 Maven 工程，自选 Spring Boot 3.4.5，不继承 spzx-parent）。
- 构建：本机未装独立 mvn，统一 `export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`。
- 测试：纯 JUnit 5（`spring-boot-starter-test`），**不引入 pytest/不联网**；单测不拉 Spring context、不连库。
- 端口：`8600`（避开 spzx 8501）。
- 库：MySQL `localhost:3306`，库名 `db_ai_brain`；口令**不写进仓库**：放 gitignore 的 `src/main/resources/application-local.yml`（模板见 Task 2）。
- 密钥只存 DB `ai_provider` 或本地 `application-local.yml`，`/console/meta` 绝不回显 apiKey。
- spec：`spzx-parent/docs/superpowers/specs/2026-10-09-ai-customer-service-design.md`（§6.5 调参试打台）。
- 输出契约口径必须一致：`{ reply, card?, intent, confidence, sources[], handoff, riskLevel }`。
- **Task 3 与 Task 4 相互引用**：先做 Task 4 的 `GenerationParams`/`RagParams` 两个 record，Task 3 才能编译通过；执行时以「Task 1 → Task 2 → Task 4 → Task 3 → Task 5 …」为准。

## File Structure

新建工程 `spzx-ai-brain/`：

```
spzx-ai-brain/
├── pom.xml
├── .gitignore
├── README.md
├── src/main/java/com/joker/aibrain/
│   ├── AiBrainApplication.java
│   ├── canonical/        AiRequest AiResponse CanonicalMessage MessageRole Channel
│   │                     Source ToolTrace TokenUsage SimContext Overrides
│   ├── runtime/          GenerationParams RagParams EffectiveConfig ConfigPayload
│   │                     ConfigMerger RuntimeConfigRepository RuntimeConfigService
│   ├── provider/         AiProvider AiProviderMapper AiProviderRepository ProviderService
│   ├── chat/             ChatInvocation ChatResult ChatInvoker SpringAiChatInvoker
│   ├── guard/            GuardrailService GuardrailVerdict
│   ├── rag/              KnowledgeRetriever InMemoryKnowledgeRetriever KnowledgeChunk
│   ├── tool/             EcomTools ToolTraceRecorder
│   ├── agent/            PromptAssembler DecisionEngine AgentPipeline
│   ├── sandbox/          SandboxSession SandboxMessage SandboxStore MyBatisSandboxStore
│   │                     OutboundGuard SandboxViolationException
│   ├── console/          ConsoleController PresetController SessionController
│   │                     ConsoleAuthInterceptor ConsoleMetaService
│   │                     AiConsolePreset AiConsolePresetMapper PresetRepository PresetService
│   └── audit/            AuditLog AuditLogMapper AuditRepository AuditService
├── src/main/resources/
│   ├── application.yml
│   ├── application-local.yml        (gitignored)
│   ├── schema.sql
│   └── knowledge/faq.md
└── src/test/java/com/joker/aibrain/   (纯 JUnit)
```

后续计划（不在本计划范围）：工具接真实 spzx Connector + pgvector RAG；试打台 SPA（Vue 3 + Vite + Element Plus）；canonical 中台 / Chatwoot Adapter / Channel Sidecar 三个子系统各自独立计划。

---

### Task 1: 工程脚手架 + 健康检查

**Files:**
- Create: `spzx-ai-brain/pom.xml`
- Create: `spzx-ai-brain/.gitignore`
- Create: `spzx-ai-brain/src/main/java/com/joker/aibrain/AiBrainApplication.java`
- Create: `spzx-ai-brain/src/main/resources/application.yml`
- Test: `spzx-ai-brain/src/test/java/com/joker/aibrain/AiBrainSmokeTest.java`

**Interfaces:**
- Consumes: 无
- Produces: 可 `mvn package` 的 Spring Boot 工程；主类 `com.joker.aibrain.AiBrainApplication`。

- [ ] **Step 1: 写 `pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.4.5</version>
        <relativePath/>
    </parent>
    <groupId>com.joker</groupId>
    <artifactId>spzx-ai-brain</artifactId>
    <version>1.0-SNAPSHOT</version>
    <name>spzx-ai-brain</name>
    <properties>
        <java.version>21</java.version>
        <spring-ai.version>1.0.0</spring-ai.version>
        <mybatis-plus.version>3.5.9</mybatis-plus.version>
    </properties>
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.ai</groupId>
                <artifactId>spring-ai-bom</artifactId>
                <version>${spring-ai.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <!-- OpenAI 兼容核心（手动构建 ChatModel，不用 starter，避免启动即需 api-key） -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-openai</artifactId>
        </dependency>
        <dependency>
            <groupId>com.baomidou</groupId>
            <artifactId>mybatis-plus-spring-boot3-starter</artifactId>
            <version>${mybatis-plus.version}</version>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

- [ ] **Step 2: 写主类**

```java
package com.joker.aibrain;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class AiBrainApplication {
    public static void main(String[] args) {
        SpringApplication.run(AiBrainApplication.class, args);
    }
}
```

- [ ] **Step 3: 写 `application.yml`**

```yaml
server:
  port: 8600

spring:
  application:
    name: spzx-ai-brain
  config:
    import: optional:classpath:application-local.yml
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://localhost:3306/db_ai_brain?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
    username: root
    password: ${SPRING_DATASOURCE_PASSWORD:}
  sql:
    init:
      mode: never
  http:
    client:
      factory: jdk

mybatis-plus:
  configuration:
    map-underscore-to-camel-case: true
  global-config:
    banner: false

management:
  endpoints:
    web:
      exposure:
        include: health,info

ai:
  console:
    token: ${AI_CONSOLE_TOKEN:dev-token}
```

- [ ] **Step 4: 写 `.gitignore`**

```
target/
*.iml
.idea/
src/main/resources/application-local.yml
```

- [ ] **Step 5: 写 smoke test（纯 JUnit，不拉 context）**

```java
package com.joker.aibrain;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class AiBrainSmokeTest {
    @Test
    void 工程可编译() {
        assertEquals("spzx-ai-brain", "spzx-ai-brain");
    }
}
```

- [ ] **Step 6: 编译并跑测试**

Run:
```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mkdir -p /Users/qyk9527/ideaProject/spzx-ai-brain
cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q -DskipTests package
mvn -q test -Dtest=AiBrainSmokeTest
```
Expected: `BUILD SUCCESS`；首次会下载 Spring AI 依赖，可能耗时数分钟。若 `spring-ai-openai` 解析失败，先 `mvn -q dependency:resolve` 排查镜像/网络，**不要擅自改版本**。

---

### Task 2: 数据库 schema + Provider 读取

**Files:**
- Create: `spzx-ai-brain/src/main/resources/schema.sql`
- Create: `spzx-ai-brain/src/main/resources/application-local.yml`（gitignored）
- Create: `spzx-ai-brain/src/main/java/com/joker/aibrain/provider/AiProvider.java`
- Create: `spzx-ai-brain/src/main/java/com/joker/aibrain/provider/AiProviderMapper.java`
- Create: `spzx-ai-brain/src/main/java/com/joker/aibrain/provider/AiProviderRepository.java`
- Create: `spzx-ai-brain/src/main/java/com/joker/aibrain/provider/MyBatisProviderRepository.java`
- Create: `spzx-ai-brain/src/main/java/com/joker/aibrain/provider/ProviderService.java`
- Test: `spzx-ai-brain/src/test/java/com/joker/aibrain/provider/ProviderServiceTest.java`

**Interfaces:**
- Produces:
  - `class AiProvider`（`@Data`）：`Long id, String name, String baseUrl, String apiKey, String textModel, String visionModel, String embeddingModel, String extraBody, Integer status, String remark`
  - `interface AiProviderRepository { List<AiProvider> listEnabled(); AiProvider byId(Long id); }`
  - `ProviderService { AiProvider resolve(Long providerId); AiProvider resolveDefault(); List<AiProvider> listEnabled(); }`

- [ ] **Step 1: 写 `schema.sql`**

```sql
CREATE DATABASE IF NOT EXISTS db_ai_brain DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE db_ai_brain;

CREATE TABLE IF NOT EXISTS ai_provider (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  base_url VARCHAR(255) NOT NULL,
  api_key VARCHAR(255),
  text_model VARCHAR(64) NOT NULL,
  vision_model VARCHAR(64),
  embedding_model VARCHAR(64),
  extra_body JSON,
  status TINYINT DEFAULT 1,
  remark VARCHAR(255),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT 'AI 引擎凭据（照搬 spzx kw_provider 模式）';

CREATE TABLE IF NOT EXISTS ai_runtime_config (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(32) NOT NULL DEFAULT 'default',
  config_json JSON NOT NULL,
  source_preset_id BIGINT,
  updated_by VARCHAR(64),
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '线上运行配置（读优先级最高）';

CREATE TABLE IF NOT EXISTS ai_console_preset (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(32) NOT NULL DEFAULT 'default',
  name VARCHAR(100) NOT NULL,
  params_json JSON NOT NULL,
  remark VARCHAR(255),
  create_by VARCHAR(64),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tenant_name (tenant_id, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '试打台命名预设';

CREATE TABLE IF NOT EXISTS ai_console_session (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id VARCHAR(32) NOT NULL DEFAULT 'default',
  title VARCHAR(120),
  is_test TINYINT DEFAULT 1,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '试打台沙盒会话（is_test=1 恒）';

CREATE TABLE IF NOT EXISTS ai_console_message (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id BIGINT NOT NULL,
  role VARCHAR(16) NOT NULL,
  content TEXT,
  meta_json JSON,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_session (session_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '试打台沙盒消息';

CREATE TABLE IF NOT EXISTS ai_audit_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  action VARCHAR(64) NOT NULL,
  target VARCHAR(64),
  detail_json JSON,
  operator VARCHAR(64),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_action_time (action, create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT 'AI Brain 审计（预设提升等）';
```

- [ ] **Step 2: 写 `application-local.yml`（不进 git）**

```yaml
spring:
  datasource:
    password: root123456
ai:
  console:
    token: dev-token
```

- [ ] **Step 3: 建库 + 导表**

```bash
python3 /Users/qyk9527/ideaProject/spzx-parent/scripts/mysql-cnf.py
mysql --defaults-extra-file=/tmp/spzx_my.cnf < /Users/qyk9527/ideaProject/spzx-ai-brain/src/main/resources/schema.sql
mysql --defaults-extra-file=/tmp/spzx_my.cnf -e "SHOW TABLES FROM db_ai_brain;"
```
Expected: 列出 6 张表（ai_provider、ai_runtime_config、ai_console_preset、ai_console_session、ai_console_message、ai_audit_log）。

- [ ] **Step 4: 写实体 + mapper**

`AiProvider.java`：
```java
package com.joker.aibrain.provider;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_provider")
public class AiProvider {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String name;
    private String baseUrl;
    private String apiKey;
    private String textModel;
    private String visionModel;
    private String embeddingModel;
    private String extraBody;
    private Integer status;
    private String remark;
}
```

`AiProviderMapper.java`：
```java
package com.joker.aibrain.provider;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AiProviderMapper extends BaseMapper<AiProvider> {
}
```

- [ ] **Step 5: 写 repository 接口 + MyBatis 实现**

`AiProviderRepository.java`：
```java
package com.joker.aibrain.provider;

import java.util.List;

public interface AiProviderRepository {
    List<AiProvider> listEnabled();
    AiProvider byId(Long id);
}
```

`MyBatisProviderRepository.java`：
```java
package com.joker.aibrain.provider;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class MyBatisProviderRepository implements AiProviderRepository {
    private final AiProviderMapper mapper;

    public MyBatisProviderRepository(AiProviderMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public List<AiProvider> listEnabled() {
        return mapper.selectList(new QueryWrapper<AiProvider>().eq("status", 1).orderByAsc("id"));
    }

    @Override
    public AiProvider byId(Long id) {
        return mapper.selectById(id);
    }
}
```

- [ ] **Step 6: 写 `ProviderService`**

```java
package com.joker.aibrain.provider;

import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ProviderService {
    private final AiProviderRepository repository;

    public ProviderService(AiProviderRepository repository) {
        this.repository = repository;
    }

    public List<AiProvider> listEnabled() {
        return repository.listEnabled();
    }

    public AiProvider resolve(Long providerId) {
        if (providerId != null) {
            AiProvider p = repository.byId(providerId);
            if (p != null && Integer.valueOf(1).equals(p.getStatus())) {
                return p;
            }
        }
        return resolveDefault();
    }

    public AiProvider resolveDefault() {
        List<AiProvider> enabled = repository.listEnabled();
        if (enabled.isEmpty()) {
            throw new IllegalStateException("没有可用的 AI Provider，请先在 ai_provider 表配置");
        }
        return enabled.get(0);
    }
}
```

- [ ] **Step 7: 写 `ProviderServiceTest`**

```java
package com.joker.aibrain.provider;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ProviderServiceTest {

    private AiProvider p(long id, int status) {
        AiProvider x = new AiProvider();
        x.setId(id);
        x.setStatus(status);
        x.setName("p" + id);
        return x;
    }

    @Test
    void 指定可用provider直接用() {
        AiProvider a = p(1, 1);
        AiProvider b = p(2, 1);
        ProviderService svc = new ProviderService(new FakeRepo(List.of(a, b)));
        assertSame(b, svc.resolve(2L));
    }

    @Test
    void 指定停用的回退默认() {
        AiProvider a = p(1, 1);
        ProviderService svc = new ProviderService(new FakeRepo(List.of(a)));
        assertSame(a, svc.resolve(2L));
    }

    @Test
    void 无provider时抛错() {
        ProviderService svc = new ProviderService(new FakeRepo(List.of()));
        assertThrows(IllegalStateException.class, svc::resolveDefault);
    }

    static class FakeRepo implements AiProviderRepository {
        private final List<AiProvider> all;
        FakeRepo(List<AiProvider> all) { this.all = all; }
        @Override public List<AiProvider> listEnabled() { return all; }
        @Override public AiProvider byId(Long id) {
            return all.stream().filter(x -> x.getId().equals(id)).findFirst().orElse(null);
        }
    }
}
```

- [ ] **Step 8: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=ProviderServiceTest`
Expected: `Tests run: 3, Failures: 0`。

---

### Task 4: 生成参数 / RAG 参数 / 有效配置合并

> 先于 Task 3 执行（Task 3 引用本任务的两个 record）。

**Files:**
- Create: `src/main/java/com/joker/aibrain/runtime/GenerationParams.java`
- Create: `src/main/java/com/joker/aibrain/runtime/RagParams.java`
- Create: `src/main/java/com/joker/aibrain/runtime/ConfigPayload.java`
- Create: `src/main/java/com/joker/aibrain/runtime/EffectiveConfig.java`
- Create: `src/main/java/com/joker/aibrain/runtime/ConfigMerger.java`
- Test: `src/test/java/com/joker/aibrain/runtime/ConfigMergerTest.java`

**Interfaces:**
- Produces:
  - `GenerationParams(Double temperature, Double topP, Double presencePenalty, Double frequencyPenalty, Integer seed, Integer maxTokens)` + `defaults()` + `merge(GenerationParams over)`
  - `RagParams(Integer topK, Double threshold, List<String> sources, Boolean enabled)` + `defaults()` + `merge(RagParams over)`
  - `EffectiveConfig(Long providerId, String model, GenerationParams generation, RagParams rag, String systemPrompt)` + `defaults()`
  - `ConfigMerger.applyRuntime(EffectiveConfig defaults, ConfigPayload runtime)`, `ConfigMerger.applyOverrides(EffectiveConfig base, Overrides over)`

- [ ] **Step 1: 写 `GenerationParams`**

```java
package com.joker.aibrain.runtime;

public record GenerationParams(
        Double temperature,
        Double topP,
        Double presencePenalty,
        Double frequencyPenalty,
        Integer seed,
        Integer maxTokens) {

    public static GenerationParams defaults() {
        return new GenerationParams(0.3, 0.9, 0.0, 0.0, null, 1024);
    }

    /** 用 over 的非空字段覆盖 this，over 为 null 时原样返回。 */
    public GenerationParams merge(GenerationParams over) {
        if (over == null) return this;
        return new GenerationParams(
                over.temperature != null ? over.temperature : temperature,
                over.topP != null ? over.topP : topP,
                over.presencePenalty != null ? over.presencePenalty : presencePenalty,
                over.frequencyPenalty != null ? over.frequencyPenalty : frequencyPenalty,
                over.seed != null ? over.seed : seed,
                over.maxTokens != null ? over.maxTokens : maxTokens);
    }
}
```

- [ ] **Step 2: 写 `RagParams`**

```java
package com.joker.aibrain.runtime;

import java.util.List;

public record RagParams(Integer topK, Double threshold, List<String> sources, Boolean enabled) {

    public static RagParams defaults() {
        return new RagParams(4, 0.10, List.of("faq", "product", "policy"), true);
    }

    public RagParams merge(RagParams over) {
        if (over == null) return this;
        return new RagParams(
                over.topK != null ? over.topK : topK,
                over.threshold != null ? over.threshold : threshold,
                over.sources != null ? over.sources : sources,
                over.enabled != null ? over.enabled : enabled);
    }
}
```

- [ ] **Step 3: 写 `EffectiveConfig` + `ConfigPayload`**

```java
package com.joker.aibrain.runtime;

public record EffectiveConfig(
        Long providerId,
        String model,
        GenerationParams generation,
        RagParams rag,
        String systemPrompt) {

    public static EffectiveConfig defaults() {
        return new EffectiveConfig(null, null, GenerationParams.defaults(), RagParams.defaults(), null);
    }
}
```
```java
package com.joker.aibrain.runtime;

/** 运行配置表 / 预设 JSON 的反序列化载体，字段可空表示"该项不覆盖"。 */
public record ConfigPayload(
        Long providerId,
        String model,
        GenerationParams generation,
        RagParams rag,
        String systemPrompt) {
}
```

- [ ] **Step 4: 写 `ConfigMerger`**

```java
package com.joker.aibrain.runtime;

import com.joker.aibrain.canonical.Overrides;

public final class ConfigMerger {

    private ConfigMerger() {}

    /** 线上配置覆盖代码默认值：null 表示不覆盖。 */
    public static EffectiveConfig applyRuntime(EffectiveConfig defaults, ConfigPayload runtime) {
        if (runtime == null) return defaults;
        return new EffectiveConfig(
                runtime.providerId() != null ? runtime.providerId() : defaults.providerId(),
                runtime.model() != null ? runtime.model() : defaults.model(),
                defaults.generation().merge(runtime.generation()),
                defaults.rag().merge(runtime.rag()),
                runtime.systemPrompt() != null ? runtime.systemPrompt() : defaults.systemPrompt());
    }

    /** 请求级覆盖（试打台）优先于一切。 */
    public static EffectiveConfig applyOverrides(EffectiveConfig base, Overrides over) {
        if (over == null) return base;
        return new EffectiveConfig(
                over.providerId() != null ? over.providerId() : base.providerId(),
                over.model() != null ? over.model() : base.model(),
                base.generation().merge(over.generation()),
                base.rag().merge(over.rag()),
                over.systemPrompt() != null ? over.systemPrompt() : base.systemPrompt());
    }
}
```

- [ ] **Step 5: 写 `ConfigMergerTest`**

```java
package com.joker.aibrain.runtime;

import com.joker.aibrain.canonical.Overrides;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class ConfigMergerTest {

    @Test
    void 线上配置覆盖默认值() {
        EffectiveConfig base = EffectiveConfig.defaults();
        ConfigPayload runtime = new ConfigPayload(null, "gpt-4o-mini", null, null, "你是专业客服");
        EffectiveConfig eff = ConfigMerger.applyRuntime(base, runtime);
        assertEquals("gpt-4o-mini", eff.model());
        assertEquals("你是专业客服", eff.systemPrompt());
        assertEquals(0.3, eff.generation().temperature(), 1e-9);
    }

    @Test
    void 请求覆盖优先于线上() {
        EffectiveConfig base = ConfigMerger.applyRuntime(
                EffectiveConfig.defaults(),
                new ConfigPayload(null, "m1", null, null, "线上提示词"));
        Overrides ov = new Overrides(null, "m2", new GenerationParams(0.9, null, null, null, null, null),
                new RagParams(8, null, null, null), "试打提示词", null);
        EffectiveConfig eff = ConfigMerger.applyOverrides(base, ov);
        assertEquals("m2", eff.model());
        assertEquals("试打提示词", eff.systemPrompt());
        assertEquals(0.9, eff.generation().temperature(), 1e-9);
        assertEquals(8, eff.rag().topK());
    }

    @Test
    void 空覆盖不改变任何值() {
        EffectiveConfig base = EffectiveConfig.defaults();
        EffectiveConfig eff = ConfigMerger.applyOverrides(base, Overrides.none());
        assertEquals(base.model(), eff.model());
        assertEquals(base.generation().temperature(), eff.generation().temperature(), 1e-9);
        assertNull(eff.systemPrompt());
    }
}
```

- [ ] **Step 6: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=ConfigMergerTest`
Expected: `Tests run: 3, Failures: 0`。（`Overrides` 由 Task 3 定义；若先做本任务，需先写 Task 3 的 `Overrides` 类，二者一并编译。）

---

### Task 3: canonical 会话模型

**Files:**
- Create: `src/main/java/com/joker/aibrain/canonical/Channel.java`
- Create: `src/main/java/com/joker/aibrain/canonical/MessageRole.java`
- Create: `src/main/java/com/joker/aibrain/canonical/CanonicalMessage.java`
- Create: `src/main/java/com/joker/aibrain/canonical/SimContext.java`
- Create: `src/main/java/com/joker/aibrain/canonical/Source.java`
- Create: `src/main/java/com/joker/aibrain/canonical/ToolTrace.java`
- Create: `src/main/java/com/joker/aibrain/canonical/TokenUsage.java`
- Create: `src/main/java/com/joker/aibrain/canonical/Overrides.java`
- Create: `src/main/java/com/joker/aibrain/canonical/AiRequest.java`
- Create: `src/main/java/com/joker/aibrain/canonical/AiResponse.java`

**Interfaces:**
- Consumes: `GenerationParams`、`RagParams`（Task 4 已定义）
- Produces: 见下方完整定义。

- [ ] **Step 1: 写枚举**

```java
package com.joker.aibrain.canonical;

public enum Channel { NATIVE, WECHAT, MINIPROGRAM, DOUYIN, TAOBAO, PDD }
```
```java
package com.joker.aibrain.canonical;

public enum MessageRole { BUYER, AGENT, AI, SYSTEM }
```

- [ ] **Step 2: 写基础记录类型**

```java
package com.joker.aibrain.canonical;

import java.time.Instant;

public record CanonicalMessage(MessageRole role, String content, Instant at) {
    public static CanonicalMessage of(MessageRole role, String content) {
        return new CanonicalMessage(role, content, Instant.now());
    }
}
```
```java
package com.joker.aibrain.canonical;

public record SimContext(String orderNo, String buyerId, String shopId) {
    public static SimContext empty() { return new SimContext(null, null, null); }
}
```
```java
package com.joker.aibrain.canonical;

public record Source(String id, String title, String snippet, double score) {}
```
```java
package com.joker.aibrain.canonical;

public record ToolTrace(String name, String input, String output, long elapsedMs) {}
```
```java
package com.joker.aibrain.canonical;

public record TokenUsage(Integer promptTokens, Integer completionTokens, Integer totalTokens) {
    public static TokenUsage empty() { return new TokenUsage(null, null, null); }
}
```

- [ ] **Step 3: 写 `Overrides`（试打参数覆盖）**

```java
package com.joker.aibrain.canonical;

import com.joker.aibrain.runtime.GenerationParams;
import com.joker.aibrain.runtime.RagParams;

public record Overrides(
        Long providerId,
        String model,
        GenerationParams generation,
        RagParams rag,
        String systemPrompt,
        Boolean toolsLocked) {
    public static Overrides none() {
        return new Overrides(null, null, null, null, null, null);
    }
}
```

- [ ] **Step 4: 写 `AiRequest`**

```java
package com.joker.aibrain.canonical;

import java.util.List;

public record AiRequest(
        String tenantId,
        Channel channel,
        Long providerId,
        String shopId,
        String contactId,
        List<CanonicalMessage> messages,
        SimContext sim,
        Overrides overrides,
        boolean sandbox) {

    public AiRequest {
        if (tenantId == null || tenantId.isBlank()) tenantId = "default";
        if (channel == null) channel = Channel.NATIVE;
        if (messages == null) messages = List.of();
        if (sim == null) sim = SimContext.empty();
        if (overrides == null) overrides = Overrides.none();
    }

    public String lastBuyerText() {
        for (int i = messages.size() - 1; i >= 0; i--) {
            CanonicalMessage m = messages.get(i);
            if (m.role() == MessageRole.BUYER) return m.content();
        }
        return messages.isEmpty() ? "" : messages.get(messages.size() - 1).content();
    }
}
```

- [ ] **Step 5: 写 `AiResponse`（输出契约 + 诊断）**

```java
package com.joker.aibrain.canonical;

import java.util.List;

public record AiResponse(
        String reply,
        Object card,
        String intent,
        double confidence,
        List<Source> sources,
        boolean handoff,
        String riskLevel,
        String decision,
        long elapsedMs,
        TokenUsage usage,
        List<ToolTrace> toolTrace,
        String assembledPrompt) {
}
```

- [ ] **Step 6: 编译验证**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q -DskipTests compile`
Expected: `BUILD SUCCESS`。

---

### Task 5: ChatInvoker 抽象 + Spring AI 实现

**Files:**
- Create: `src/main/java/com/joker/aibrain/chat/ChatMessage.java`
- Create: `src/main/java/com/joker/aibrain/chat/ChatInvocation.java`
- Create: `src/main/java/com/joker/aibrain/chat/ChatResult.java`
- Create: `src/main/java/com/joker/aibrain/chat/ChatInvoker.java`
- Create: `src/main/java/com/joker/aibrain/chat/SpringAiChatInvoker.java`
- Test: `src/test/java/com/joker/aibrain/chat/FakeChatInvoker.java`
- Test: `src/test/java/com/joker/aibrain/chat/FakeChatInvokerTest.java`

**Interfaces:**
- Consumes: `AiProvider`、`GenerationParams`、`TokenUsage`
- Produces:
  - `record ChatMessage(String role, String content)` + 静态工厂 `system/user/assistant`
  - `record ChatInvocation(AiProvider provider, String model, GenerationParams generation, List<ChatMessage> messages, List<Object> tools)`
  - `record ChatResult(String text, TokenUsage usage)`
  - `interface ChatInvoker { ChatResult invoke(ChatInvocation inv); }`
- **设计要点（降低 Spring AI API 风险）**：只有 `SpringAiChatInvoker` 一处直接依赖 Spring AI；上层与测试全走 `ChatInvoker` 接口。

- [ ] **Step 1: 写三个 record**

```java
package com.joker.aibrain.chat;

public record ChatMessage(String role, String content) {
    public static ChatMessage system(String c) { return new ChatMessage("system", c); }
    public static ChatMessage user(String c) { return new ChatMessage("user", c); }
    public static ChatMessage assistant(String c) { return new ChatMessage("assistant", c); }
}
```
```java
package com.joker.aibrain.chat;

import com.joker.aibrain.provider.AiProvider;
import com.joker.aibrain.runtime.GenerationParams;

import java.util.List;

public record ChatInvocation(
        AiProvider provider,
        String model,
        GenerationParams generation,
        List<ChatMessage> messages,
        List<Object> tools) {
}
```
```java
package com.joker.aibrain.chat;

import com.joker.aibrain.canonical.TokenUsage;

public record ChatResult(String text, TokenUsage usage) {
}
```

- [ ] **Step 2: 写接口**

```java
package com.joker.aibrain.chat;

public interface ChatInvoker {
    ChatResult invoke(ChatInvocation inv);
}
```

- [ ] **Step 3: 写 Spring AI 实现**

```java
package com.joker.aibrain.chat;

import com.joker.aibrain.canonical.TokenUsage;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.openai.OpenAiChatModel;
import org.springframework.ai.openai.OpenAiChatOptions;
import org.springframework.ai.openai.api.OpenAiApi;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class SpringAiChatInvoker implements ChatInvoker {

    @Override
    public ChatResult invoke(ChatInvocation inv) {
        OpenAiApi api = OpenAiApi.builder()
                .baseUrl(inv.provider().getBaseUrl())
                .apiKey(inv.provider().getApiKey())
                .build();

        OpenAiChatOptions.Builder optionsBuilder = OpenAiChatOptions.builder()
                .model(inv.model() != null ? inv.model() : inv.provider().getTextModel())
                .temperature(inv.generation().temperature())
                .topP(inv.generation().topP())
                .maxTokens(inv.generation().maxTokens());
        if (inv.generation().presencePenalty() != null) optionsBuilder.presencePenalty(inv.generation().presencePenalty());
        if (inv.generation().frequencyPenalty() != null) optionsBuilder.frequencyPenalty(inv.generation().frequencyPenalty());
        if (inv.generation().seed() != null) optionsBuilder.seed(inv.generation().seed());
        OpenAiChatOptions options = optionsBuilder.build();

        ChatModel model = OpenAiChatModel.builder()
                .openAiApi(api)
                .defaultOptions(options)
                .build();

        List<Message> messages = new ArrayList<>();
        for (ChatMessage m : inv.messages()) {
            messages.add(toSpring(m));
        }

        ChatClient client = ChatClient.builder(model).build();
        ChatResponse response = client.prompt()
                .messages(messages.toArray(new Message[0]))
                .tools(inv.tools().toArray())
                .call()
                .chatResponse();

        String text = response.getResult().getOutput().getText();
        Usage u = response.getMetadata().getUsage();
        TokenUsage usage = u == null ? TokenUsage.empty()
                : new TokenUsage(u.getPromptTokens(), u.getCompletionTokens(), u.getTotalTokens());
        return new ChatResult(text, usage);
    }

    private Message toSpring(ChatMessage m) {
        return switch (m.role()) {
            case "system" -> new SystemMessage(m.content());
            case "assistant" -> new AssistantMessage(m.content());
            default -> new UserMessage(m.content());
        };
    }
}
```

- [ ] **Step 4: 编译验证 API**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q -DskipTests compile`
Expected: `BUILD SUCCESS`。若报方法/包名不符（如 `messages(...)`、`getText()`），按 Spring AI 1.0.x JavaDoc 修正**本文件内**调用；**不要**改 `ChatInvoker` 接口签名。

- [ ] **Step 5: 写测试替身 `FakeChatInvoker`**

```java
package com.joker.aibrain.chat;

import com.joker.aibrain.canonical.TokenUsage;

import java.util.ArrayList;
import java.util.List;

public class FakeChatInvoker implements ChatInvoker {
    private final String cannedReply;
    public final List<ChatInvocation> invocations = new ArrayList<>();

    public FakeChatInvoker(String cannedReply) {
        this.cannedReply = cannedReply;
    }

    @Override
    public ChatResult invoke(ChatInvocation inv) {
        invocations.add(inv);
        return new ChatResult(cannedReply, new TokenUsage(10, 20, 30));
    }

    public ChatInvocation last() {
        return invocations.get(invocations.size() - 1);
    }
}
```

- [ ] **Step 6: 写替身自测**

```java
package com.joker.aibrain.chat;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FakeChatInvokerTest {
    @Test
    void 替身记录调用并返回固定回复() {
        FakeChatInvoker fake = new FakeChatInvoker("你好");
        ChatResult r = fake.invoke(new ChatInvocation(null, "m", null,
                List.of(ChatMessage.user("hi")), List.of()));
        assertEquals("你好", r.text());
        assertEquals(30, r.usage().totalTokens());
        assertTrue(fake.invocations.size() == 1);
    }
}
```

- [ ] **Step 7: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=FakeChatInvokerTest`
Expected: `Tests run: 1, Failures: 0`。

---

### Task 6: 护栏（高风险意图 + 禁词合规）

**Files:**
- Create: `src/main/java/com/joker/aibrain/guard/GuardrailVerdict.java`
- Create: `src/main/java/com/joker/aibrain/guard/GuardrailService.java`
- Test: `src/test/java/com/joker/aibrain/guard/GuardrailServiceTest.java`

**Interfaces:**
- Produces:
  - `record GuardrailVerdict(String intent, boolean highRisk, List<String> riskHits, List<String> forbiddenHits)`
  - `GuardrailService { GuardrailVerdict evaluate(String buyerText); List<String> forbiddenHits(String reply); }`

- [ ] **Step 1: 写 `GuardrailVerdict`**

```java
package com.joker.aibrain.guard;

import java.util.List;

public record GuardrailVerdict(
        String intent,
        boolean highRisk,
        List<String> riskHits,
        List<String> forbiddenHits) {
}
```

- [ ] **Step 2: 写 `GuardrailService`**

```java
package com.joker.aibrain.guard;

import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class GuardrailService {

    /** 高风险意图关键词 → 意图名。命中任意一个 → 强制转人工。 */
    private static final Map<String, List<String>> RISK_KEYWORDS = new LinkedHashMap<>();
    static {
        RISK_KEYWORDS.put("complaint", List.of("投诉", "举报", "曝光", "差评", "工商", "12315", "315", "欺诈", "骗子", "违法"));
        RISK_KEYWORDS.put("refund", List.of("退款", "退货", "退钱", "仅退款", "赔偿", "索赔"));
    }

    /** 输出合规禁词（平台合规 / 广告法极限词）。 */
    private static final List<String> FORBIDDEN = List.of(
            "绝对", "保证", "100%", "百分百", "最低价", "最便宜", "包治", "稳赚", "国家级", "世界级");

    public GuardrailVerdict evaluate(String buyerText) {
        String text = buyerText == null ? "" : buyerText;
        for (Map.Entry<String, List<String>> e : RISK_KEYWORDS.entrySet()) {
            List<String> hits = hits(text, e.getValue());
            if (!hits.isEmpty()) {
                return new GuardrailVerdict(e.getKey(), true, hits, List.of());
            }
        }
        return new GuardrailVerdict("general", false, List.of(), List.of());
    }

    public List<String> forbiddenHits(String reply) {
        return hits(reply == null ? "" : reply, FORBIDDEN);
    }

    private List<String> hits(String text, List<String> words) {
        List<String> out = new ArrayList<>();
        for (String w : words) {
            if (text.contains(w)) out.add(w);
        }
        return out;
    }
}
```

- [ ] **Step 3: 写 `GuardrailServiceTest`**

```java
package com.joker.aibrain.guard;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GuardrailServiceTest {

    private final GuardrailService svc = new GuardrailService();

    @Test
    void 退款意图判为高风险并要求转人工() {
        GuardrailVerdict v = svc.evaluate("我要退款，东西不好");
        assertTrue(v.highRisk());
        assertEquals("refund", v.intent());
        assertTrue(v.riskHits().contains("退款"));
    }

    @Test
    void 投诉优先命中complaint() {
        GuardrailVerdict v = svc.evaluate("再不解决我就投诉了");
        assertTrue(v.highRisk());
        assertEquals("complaint", v.intent());
    }

    @Test
    void 普通问题不是高风险() {
        GuardrailVerdict v = svc.evaluate("这个尺码偏大吗？");
        assertFalse(v.highRisk());
        assertEquals("general", v.intent());
    }

    @Test
    void 禁词命中可检出() {
        assertTrue(svc.forbiddenHits("这是全网最低价，绝对保证有效").contains("绝对"));
        assertTrue(svc.forbiddenHits("这是全网最低价，绝对保证有效").contains("最低价"));
        assertTrue(svc.forbiddenHits("正常话术").isEmpty());
    }
}
```

- [ ] **Step 4: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=GuardrailServiceTest`
Expected: `Tests run: 4, Failures: 0`。

---

### Task 7: RAG 检索（naive 内存实现，向量库后置）

**Files:**
- Create: `src/main/java/com/joker/aibrain/rag/KnowledgeChunk.java`
- Create: `src/main/java/com/joker/aibrain/rag/KnowledgeRetriever.java`
- Create: `src/main/java/com/joker/aibrain/rag/InMemoryKnowledgeRetriever.java`
- Create: `src/main/resources/knowledge/faq.md`
- Test: `src/test/java/com/joker/aibrain/rag/InMemoryKnowledgeRetrieverTest.java`

**Interfaces:**
- Consumes: `RagParams`、`Source`
- Produces:
  - `record KnowledgeChunk(String id, String sourceType, String title, String text)`
  - `interface KnowledgeRetriever { List<Source> retrieve(String query, RagParams params); }`
- **说明**：Phase A 先用内存检索（中文 bigram 重叠打分），pgvector 在后续计划替换；接口不变。

- [ ] **Step 1: 写 `KnowledgeChunk` + 接口**

```java
package com.joker.aibrain.rag;

public record KnowledgeChunk(String id, String sourceType, String title, String text) {
}
```
```java
package com.joker.aibrain.rag;

import com.joker.aibrain.canonical.Source;
import com.joker.aibrain.runtime.RagParams;

import java.util.List;

public interface KnowledgeRetriever {
    List<Source> retrieve(String query, RagParams params);
}
```

- [ ] **Step 2: 写 seed 知识文件**

`src/main/resources/knowledge/faq.md`：
```markdown
# 发货时效
正常情况下付款后 48 小时内发货，预售商品以详情页标注为准。

# 退换货政策
七天无理由退换，商品需保持吊牌完整、不影响二次销售。贴身衣物拆封后不支持无理由退换。

# 尺码建议
家居服/睡衣偏宽松，建议按日常尺码选择；如介于两个码之间选大一码。
```

- [ ] **Step 3: 写 `InMemoryKnowledgeRetriever`**

```java
package com.joker.aibrain.rag;

import com.joker.aibrain.canonical.Source;
import com.joker.aibrain.runtime.RagParams;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Component
public class InMemoryKnowledgeRetriever implements KnowledgeRetriever {

    private final List<KnowledgeChunk> chunks;

    public InMemoryKnowledgeRetriever() {
        this.chunks = loadSeed();
    }

    /** 测试用：显式传入 chunk。 */
    public InMemoryKnowledgeRetriever(List<KnowledgeChunk> chunks) {
        this.chunks = chunks;
    }

    @Override
    public List<Source> retrieve(String query, RagParams params) {
        if (params == null || Boolean.FALSE.equals(params.enabled())) {
            return List.of();
        }
        Set<String> q = bigrams(query);
        if (q.isEmpty()) return List.of();

        List<Source> scored = new ArrayList<>();
        for (KnowledgeChunk c : chunks) {
            if (params.sources() != null && !params.sources().isEmpty()
                    && !params.sources().contains(c.sourceType())) {
                continue;
            }
            Set<String> cb = bigrams(c.text());
            int hit = 0;
            for (String g : q) if (cb.contains(g)) hit++;
            double score = cb.isEmpty() ? 0 : (double) hit / cb.size();
            if (score >= params.threshold()) {
                scored.add(new Source(c.id(), c.title(), c.text(), round(score)));
            }
        }
        scored.sort(Comparator.comparingDouble(Source::score).reversed());
        int k = params.topK() == null ? 4 : params.topK();
        return scored.size() > k ? new ArrayList<>(scored.subList(0, k)) : scored;
    }

    private static double round(double d) {
        return Math.round(d * 10000d) / 10000d;
    }

    private static Set<String> bigrams(String s) {
        String t = s == null ? "" : s.replaceAll("\\s+", "");
        Set<String> set = new HashSet<>();
        for (int i = 0; i + 1 < t.length(); i++) set.add(t.substring(i, i + 2));
        return set;
    }

    private static List<KnowledgeChunk> loadSeed() {
        List<KnowledgeChunk> list = new ArrayList<>();
        try {
            Resource[] resources = new PathMatchingResourcePatternResolver()
                    .getResources("classpath*:knowledge/*.md");
            for (Resource r : resources) {
                String content = new String(r.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
                String[] blocks = content.split("\\n\\n+");
                int i = 0;
                for (String b : blocks) {
                    String tb = b.trim();
                    if (tb.isEmpty()) continue;
                    String title = tb.startsWith("#") ? tb.substring(tb.indexOf(' ') + 1).split("\\n")[0] : "faq";
                    list.add(new KnowledgeChunk("faq-" + (i++), "faq", title, tb));
                }
            }
        } catch (Exception ignored) {
            // 无 seed 文件时返回空库
        }
        return list;
    }
}
```

- [ ] **Step 4: 写 `InMemoryKnowledgeRetrieverTest`**

```java
package com.joker.aibrain.rag;

import com.joker.aibrain.canonical.Source;
import com.joker.aibrain.runtime.RagParams;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class InMemoryKnowledgeRetrieverTest {

    private final InMemoryKnowledgeRetriever retriever = new InMemoryKnowledgeRetriever(List.of(
            new KnowledgeChunk("1", "faq", "发货", "付款后 48 小时内发货"),
            new KnowledgeChunk("2", "policy", "退货", "七天无理由退换货政策")
    ));

    @Test
    void 检索发货问题命中发货片段() {
        List<Source> out = retriever.retrieve("什么时候发货", new RagParams(4, 0.05, null, true));
        assertTrue(out.stream().anyMatch(s -> s.title().equals("发货")));
    }

    @Test
    void 关闭RAG时返回空() {
        List<Source> out = retriever.retrieve("什么时候发货", new RagParams(4, 0.05, null, false));
        assertEquals(0, out.size());
    }

    @Test
    void 知识源开关过滤() {
        List<Source> out = retriever.retrieve("发货 退货", new RagParams(4, 0.0, List.of("policy"), true));
        assertTrue(out.stream().allMatch(s -> s.id().equals("2")));
    }

    @Test
    void topK限制条数() {
        List<Source> out = retriever.retrieve("发货 退货", new RagParams(1, 0.0, null, true));
        assertEquals(1, out.size());
    }
}
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=InMemoryKnowledgeRetrieverTest`
Expected: `Tests run: 4, Failures: 0`。

---

### Task 8: 电商工具（只读 stub）+ 调用轨迹 + 沙盒锁定

**Files:**
- Create: `src/main/java/com/joker/aibrain/tool/ToolTraceRecorder.java`
- Create: `src/main/java/com/joker/aibrain/tool/EcomTools.java`
- Test: `src/test/java/com/joker/aibrain/tool/EcomToolsTest.java`

**Interfaces:**
- Consumes: `SimContext`、`ToolTrace`
- Produces:
  - `ToolTraceRecorder { void record(String name, String input, String output, long ms); List<ToolTrace> traces(); }`
  - `EcomTools(ToolTraceRecorder recorder, SimContext sim, boolean locked)`，方法带 `@Tool`：`queryOrder`、`queryLogistics`、`queryProduct`、`recommendProduct`、`escalateToHuman`、`tagConversation`
- **说明**：本任务工具返回**固定只读 mock 数据**，真实 spzx Connector 后续计划替换；`locked=true` 时强行用 `sim` 里的订单号。

- [ ] **Step 1: 写 `ToolTraceRecorder`**

```java
package com.joker.aibrain.tool;

import com.joker.aibrain.canonical.ToolTrace;

import java.util.ArrayList;
import java.util.List;

public class ToolTraceRecorder {
    private final List<ToolTrace> traces = new ArrayList<>();

    public void record(String name, String input, String output, long ms) {
        traces.add(new ToolTrace(name, input, output, ms));
    }

    public List<ToolTrace> traces() {
        return List.copyOf(traces);
    }
}
```

- [ ] **Step 2: 写 `EcomTools`**

```java
package com.joker.aibrain.tool;

import com.joker.aibrain.canonical.SimContext;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;

public class EcomTools {

    private final ToolTraceRecorder recorder;
    private final SimContext sim;
    private final boolean locked;

    public EcomTools(ToolTraceRecorder recorder, SimContext sim, boolean locked) {
        this.recorder = recorder;
        this.sim = sim == null ? SimContext.empty() : sim;
        this.locked = locked;
    }

    private String orderKey(String orderNo) {
        if (locked) {
            return sim.orderNo() != null ? sim.orderNo() : "UNKNOWN";
        }
        return orderNo;
    }

    @Tool(description = "查询买家的订单状态。参数为订单号；未提供则用当前会话订单号。")
    public String queryOrder(@ToolParam(description = "订单号", required = false) String orderNo) {
        String key = orderKey(orderNo);
        String out = "{\"orderNo\":\"" + (key == null ? "UNKNOWN" : key)
                + "\",\"status\":\"已发货\",\"mock\":true}";
        recorder.record("query_order", String.valueOf(key), out, 3);
        return out;
    }

    @Tool(description = "查询订单物流轨迹。参数为订单号。")
    public String queryLogistics(@ToolParam(description = "订单号", required = false) String orderNo) {
        String key = orderKey(orderNo);
        String out = "{\"orderNo\":\"" + (key == null ? "UNKNOWN" : key)
                + "\",\"traces\":[\"已揽收\",\"运输中\"],\"mock\":true}";
        recorder.record("query_logistics", String.valueOf(key), out, 3);
        return out;
    }

    @Tool(description = "按关键词或 SKU 查询商品信息、库存、尺码。")
    public String queryProduct(@ToolParam(description = "关键词或SKU") String keyword) {
        String out = "{\"keyword\":\"" + keyword + "\",\"stock\":100,\"mock\":true}";
        recorder.record("query_product", keyword, out, 3);
        return out;
    }

    @Tool(description = "根据买家需求推荐商品。")
    public String recommendProduct(@ToolParam(description = "买家需求描述") String need) {
        String out = "{\"need\":\"" + need + "\",\"recommend\":[\"商品A\",\"商品B\"],\"mock\":true}";
        recorder.record("recommend_product", need, out, 3);
        return out;
    }

    @Tool(description = "转人工，并附 AI 摘要。")
    public String escalateToHuman(
            @ToolParam(description = "转人工原因") String reason,
            @ToolParam(description = "AI 摘要", required = false) String summary) {
        String out = "{\"escalated\":true,\"reason\":\"" + reason + "\",\"mock\":true}";
        recorder.record("escalate_to_human", reason, out, 3);
        return out;
    }

    @Tool(description = "给会话打标签，便于统计。")
    public String tagConversation(@ToolParam(description = "标签，逗号分隔") String tag) {
        recorder.record("tag_conversation", tag, "{\"ok\":true}", 3);
        return "{\"ok\":true,\"tag\":\"" + tag + "\"}";
    }
}
```

- [ ] **Step 3: 写 `EcomToolsTest`**

```java
package com.joker.aibrain.tool;

import com.joker.aibrain.canonical.SimContext;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EcomToolsTest {

    @Test
    void 每次调用都记录轨迹() {
        ToolTraceRecorder rec = new ToolTraceRecorder();
        EcomTools tools = new EcomTools(rec, SimContext.empty(), false);
        tools.queryOrder("A123");
        assertEquals(1, rec.traces().size());
        assertEquals("query_order", rec.traces().get(0).name());
        assertTrue(rec.traces().get(0).output().contains("A123"));
    }

    @Test
    void 锁定时强制用模拟订单号() {
        ToolTraceRecorder rec = new ToolTraceRecorder();
        EcomTools tools = new EcomTools(rec, new SimContext("SIM-1", "buyer1", "shop1"), true);
        String out = tools.queryOrder("REAL-999");
        assertTrue(out.contains("SIM-1"));
        assertFalse(out.contains("REAL-999"));
    }

    @Test
    void 不锁定时用传入订单号() {
        ToolTraceRecorder rec = new ToolTraceRecorder();
        EcomTools tools = new EcomTools(rec, new SimContext("SIM-1", null, null), false);
        assertTrue(tools.queryLogistics("REAL-999").contains("REAL-999"));
    }
}
```

- [ ] **Step 4: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=EcomToolsTest`
Expected: `Tests run: 3, Failures: 0`。

---

### Task 9: 提示词装配

**Files:**
- Create: `src/main/java/com/joker/aibrain/agent/PromptAssembler.java`
- Test: `src/test/java/com/joker/aibrain/agent/PromptAssemblerTest.java`

**Interfaces:**
- Consumes: `EffectiveConfig`、`AiRequest`、`List<Source>`
- Produces: `PromptAssembler { String system(EffectiveConfig eff, AiRequest req, List<Source> sources); }`

- [ ] **Step 1: 写 `PromptAssembler`**

```java
package com.joker.aibrain.agent;

import com.joker.aibrain.canonical.AiRequest;
import com.joker.aibrain.canonical.Source;
import com.joker.aibrain.runtime.EffectiveConfig;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class PromptAssembler {

    private static final String DEFAULT_SYSTEM = """
            你是一名专业、耐心、口语化的电商客服。回答要求：
            1. 只依据提供的知识片段和工具返回作答，不确定就说明并建议转人工；
            2. 不承诺退款金额、不承诺具体时效、不编造物流、不泄露内部信息；
            3. 不使用绝对化/极限词；
            4. 回复简洁，先给结论再给必要说明。
            """;

    public String system(EffectiveConfig eff, AiRequest req, List<Source> sources) {
        String base = (eff.systemPrompt() != null && !eff.systemPrompt().isBlank())
                ? eff.systemPrompt() : DEFAULT_SYSTEM;

        StringBuilder sb = new StringBuilder(base.trim());

        if (req != null && req.sim() != null) {
            sb.append("\n\n[当前模拟上下文]")
              .append("\n店铺=").append(nvl(req.sim().shopId()))
              .append(" 买家=").append(nvl(req.sim().buyerId()))
              .append(" 订单号=").append(nvl(req.sim().orderNo()));
        }

        if (sources != null && !sources.isEmpty()) {
            sb.append("\n\n[可参考的知识片段]");
            for (Source s : sources) {
                sb.append("\n- (").append(s.title()).append(") ").append(s.snippet());
            }
        }

        sb.append("\n\n[工具]当需要订单/物流/商品信息时，调用提供的工具获取，不要凭空编造。");
        return sb.toString();
    }

    private static String nvl(String s) {
        return s == null ? "-" : s;
    }
}
```

- [ ] **Step 2: 写 `PromptAssemblerTest`**

```java
package com.joker.aibrain.agent;

import com.joker.aibrain.canonical.AiRequest;
import com.joker.aibrain.canonical.Channel;
import com.joker.aibrain.canonical.SimContext;
import com.joker.aibrain.canonical.Source;
import com.joker.aibrain.runtime.EffectiveConfig;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PromptAssemblerTest {

    private final PromptAssembler assembler = new PromptAssembler();

    private AiRequest req() {
        return new AiRequest("default", Channel.NATIVE, null, "shop1", "c1", List.of(),
                new SimContext("SIM-1", "buyer1", "shop1"), null, true);
    }

    @Test
    void 覆盖提示词生效并拼入知识片段() {
        EffectiveConfig eff = new EffectiveConfig(null, null,
                com.joker.aibrain.runtime.GenerationParams.defaults(),
                com.joker.aibrain.runtime.RagParams.defaults(), "你是睡衣店客服");
        String system = assembler.system(eff, req(), List.of(new Source("1", "发货", "48小时发货", 0.9)));
        assertTrue(system.contains("你是睡衣店客服"));
        assertTrue(system.contains("48小时发货"));
        assertTrue(system.contains("SIM-1"));
    }

    @Test
    void 无覆盖时用默认且不含知识段() {
        String system = assembler.system(EffectiveConfig.defaults(), req(), List.of());
        assertTrue(system.contains("电商客服"));
        assertFalse(system.contains("可参考的知识片段"));
    }
}
```

- [ ] **Step 3: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=PromptAssemblerTest`
Expected: `Tests run: 2, Failures: 0`。

---

### Task 10: 决策引擎

**Files:**
- Create: `src/main/java/com/joker/aibrain/agent/DecisionEngine.java`
- Test: `src/test/java/com/joker/aibrain/agent/DecisionEngineTest.java`

**Interfaces:**
- Consumes: `GuardrailVerdict`、`Channel`
- Produces: `DecisionEngine { String decide(GuardrailVerdict g, double confidence, Channel channel); }`，返回常量 `AUTO`/`DRAFT`/`HANDOFF`。

- [ ] **Step 1: 写 `DecisionEngine`**

```java
package com.joker.aibrain.agent;

import com.joker.aibrain.canonical.Channel;
import com.joker.aibrain.guard.GuardrailVerdict;
import org.springframework.stereotype.Component;

@Component
public class DecisionEngine {

    public static final String AUTO = "AUTO";
    public static final String DRAFT = "DRAFT";
    public static final String HANDOFF = "HANDOFF";

    public static final double AUTO_CONFIDENCE = 0.80;

    public String decide(GuardrailVerdict g, double confidence, Channel channel) {
        if (g != null && g.highRisk()) {
            return HANDOFF;
        }
        if (channel == Channel.NATIVE && confidence >= AUTO_CONFIDENCE) {
            return AUTO;
        }
        return DRAFT;
    }
}
```

- [ ] **Step 2: 写 `DecisionEngineTest`**

```java
package com.joker.aibrain.agent;

import com.joker.aibrain.canonical.Channel;
import com.joker.aibrain.guard.GuardrailVerdict;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DecisionEngineTest {

    private final DecisionEngine engine = new DecisionEngine();
    private final GuardrailVerdict low = new GuardrailVerdict("general", false, List.of(), List.of());
    private final GuardrailVerdict high = new GuardrailVerdict("refund", true, List.of("退款"), List.of());

    @Test
    void 高风险一律转人工() {
        assertEquals(DecisionEngine.HANDOFF, engine.decide(high, 0.99, Channel.NATIVE));
        assertEquals(DecisionEngine.HANDOFF, engine.decide(high, 0.99, Channel.TAOBAO));
    }

    @Test
    void 原生高置信自动回复() {
        assertEquals(DecisionEngine.AUTO, engine.decide(low, 0.85, Channel.NATIVE));
    }

    @Test
    void 原生低置信拟稿() {
        assertEquals(DecisionEngine.DRAFT, engine.decide(low, 0.5, Channel.NATIVE));
    }

    @Test
    void 电商渠道即使高置信也只拟稿() {
        assertEquals(DecisionEngine.DRAFT, engine.decide(low, 0.99, Channel.DOUYIN));
        assertEquals(DecisionEngine.DRAFT, engine.decide(low, 0.99, Channel.TAOBAO));
        assertEquals(DecisionEngine.DRAFT, engine.decide(low, 0.99, Channel.PDD));
    }
}
```

- [ ] **Step 3: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=DecisionEngineTest`
Expected: `Tests run: 4, Failures: 0`。

---

### Task 11: 线上运行配置读取

**Files:**
- Create: `src/main/java/com/joker/aibrain/runtime/AiRuntimeConfig.java`
- Create: `src/main/java/com/joker/aibrain/runtime/RuntimeConfigMapper.java`
- Create: `src/main/java/com/joker/aibrain/runtime/RuntimeConfigRepository.java`
- Create: `src/main/java/com/joker/aibrain/runtime/MyBatisRuntimeConfigRepository.java`
- Create: `src/main/java/com/joker/aibrain/runtime/RuntimeConfigService.java`
- Test: `src/test/java/com/joker/aibrain/runtime/RuntimeConfigServiceTest.java`

**Interfaces:**
- Produces:
  - `interface RuntimeConfigRepository { String configJson(String tenantId); }`
  - `RuntimeConfigService(RuntimeConfigRepository repository, ObjectMapper mapper)`，对 `repository == null` 容错
  - `EffectiveConfig effectiveBase(String tenantId)`：优先级 = 线上配置表 > 代码默认值

- [ ] **Step 1: 写实体 + mapper**

```java
package com.joker.aibrain.runtime;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_runtime_config")
public class AiRuntimeConfig {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String tenantId;
    private String configJson;
    private Long sourcePresetId;
    private String updatedBy;
}
```
```java
package com.joker.aibrain.runtime;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface RuntimeConfigMapper extends BaseMapper<AiRuntimeConfig> {
}
```

- [ ] **Step 2: 写 repository 接口 + 实现**

```java
package com.joker.aibrain.runtime;

public interface RuntimeConfigRepository {
    /** 返回该租户的 config_json 原文，没有则 null。 */
    String configJson(String tenantId);
}
```
```java
package com.joker.aibrain.runtime;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.springframework.stereotype.Repository;

@Repository
public class MyBatisRuntimeConfigRepository implements RuntimeConfigRepository {
    private final RuntimeConfigMapper mapper;

    public MyBatisRuntimeConfigRepository(RuntimeConfigMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public String configJson(String tenantId) {
        AiRuntimeConfig row = mapper.selectOne(
                new QueryWrapper<AiRuntimeConfig>().eq("tenant_id", tenantId).last("LIMIT 1"));
        return row == null ? null : row.getConfigJson();
    }
}
```

- [ ] **Step 3: 写 `RuntimeConfigService`**

```java
package com.joker.aibrain.runtime;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

@Service
public class RuntimeConfigService {

    private final RuntimeConfigRepository repository;
    private final ObjectMapper mapper;

    public RuntimeConfigService(RuntimeConfigRepository repository, ObjectMapper mapper) {
        this.repository = repository;
        this.mapper = mapper == null ? new ObjectMapper() : mapper;
    }

    public EffectiveConfig effectiveBase(String tenantId) {
        EffectiveConfig defaults = EffectiveConfig.defaults();
        if (repository == null) return defaults;
        String json = repository.configJson(tenantId == null ? "default" : tenantId);
        if (json == null || json.isBlank()) return defaults;
        try {
            ConfigPayload payload = mapper.readValue(json, ConfigPayload.class);
            return ConfigMerger.applyRuntime(defaults, payload);
        } catch (Exception e) {
            return defaults;
        }
    }
}
```

- [ ] **Step 4: 写 `RuntimeConfigServiceTest`**

```java
package com.joker.aibrain.runtime;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class RuntimeConfigServiceTest {

    @Test
    void 无配置时用代码默认值() {
        RuntimeConfigService svc = new RuntimeConfigService(tenant -> null, new ObjectMapper());
        EffectiveConfig eff = svc.effectiveBase("default");
        assertEquals(0.3, eff.generation().temperature(), 1e-9);
        assertNull(eff.model());
    }

    @Test
    void 有配置时覆盖模型与提示词() {
        String json = "{\"model\":\"deepseek-chat\",\"systemPrompt\":\"线上人设\",\"generation\":{\"temperature\":0.7}}";
        RuntimeConfigService svc = new RuntimeConfigService(tenant -> json, new ObjectMapper());
        EffectiveConfig eff = svc.effectiveBase("default");
        assertEquals("deepseek-chat", eff.model());
        assertEquals("线上人设", eff.systemPrompt());
        assertEquals(0.7, eff.generation().temperature(), 1e-9);
        assertEquals(1024, eff.generation().maxTokens());
    }

    @Test
    void 坏JSON回退默认不抛错() {
        RuntimeConfigService svc = new RuntimeConfigService(tenant -> "{bad json", new ObjectMapper());
        assertEquals(0.3, svc.effectiveBase("default").generation().temperature(), 1e-9);
    }
}
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=RuntimeConfigServiceTest`
Expected: `Tests run: 3, Failures: 0`。

---

### Task 12: AgentPipeline 编排（含沙盒出站短路）

**Files:**
- Create: `src/main/java/com/joker/aibrain/sandbox/SandboxViolationException.java`
- Create: `src/main/java/com/joker/aibrain/sandbox/OutboundGuard.java`
- Create: `src/main/java/com/joker/aibrain/agent/AgentPipeline.java`
- Test: `src/test/java/com/joker/aibrain/sandbox/OutboundGuardTest.java`
- Test: `src/test/java/com/joker/aibrain/agent/AgentPipelineTest.java`

**Interfaces:**
- Consumes: `ProviderService`、`RuntimeConfigService`、`ConfigMerger`、`GuardrailService`、`KnowledgeRetriever`、`PromptAssembler`、`DecisionEngine`、`ChatInvoker`、`EcomTools`
- Produces:
  - `AiResponse AgentPipeline.run(AiRequest req)`
  - `OutboundGuard { void assertAllowed(boolean sandbox); }`

- [ ] **Step 1: 写 `SandboxViolationException` + `OutboundGuard`**

```java
package com.joker.aibrain.sandbox;

public class SandboxViolationException extends RuntimeException {
    public SandboxViolationException(String message) {
        super(message);
    }
}
```
```java
package com.joker.aibrain.sandbox;

import org.springframework.stereotype.Component;

/** 所有对外发送（Sidecar / Gateway / 平台）前的统一闸门。沙盒请求在此被硬拦。 */
@Component
public class OutboundGuard {

    public void assertAllowed(boolean sandbox) {
        if (sandbox) {
            throw new SandboxViolationException("沙盒试打禁止任何外发（OutboundGuard 短路）");
        }
    }
}
```

- [ ] **Step 2: 写 `AgentPipeline`**

```java
package com.joker.aibrain.agent;

import com.joker.aibrain.canonical.AiRequest;
import com.joker.aibrain.canonical.AiResponse;
import com.joker.aibrain.canonical.CanonicalMessage;
import com.joker.aibrain.canonical.MessageRole;
import com.joker.aibrain.canonical.Source;
import com.joker.aibrain.canonical.TokenUsage;
import com.joker.aibrain.chat.ChatInvoker;
import com.joker.aibrain.chat.ChatInvocation;
import com.joker.aibrain.chat.ChatMessage;
import com.joker.aibrain.chat.ChatResult;
import com.joker.aibrain.guard.GuardrailService;
import com.joker.aibrain.guard.GuardrailVerdict;
import com.joker.aibrain.provider.AiProvider;
import com.joker.aibrain.provider.ProviderService;
import com.joker.aibrain.rag.KnowledgeRetriever;
import com.joker.aibrain.runtime.ConfigMerger;
import com.joker.aibrain.runtime.EffectiveConfig;
import com.joker.aibrain.runtime.RuntimeConfigService;
import com.joker.aibrain.tool.EcomTools;
import com.joker.aibrain.tool.ToolTraceRecorder;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class AgentPipeline {

    private final ProviderService providerService;
    private final RuntimeConfigService runtimeConfigService;
    private final GuardrailService guardrailService;
    private final KnowledgeRetriever retriever;
    private final PromptAssembler promptAssembler;
    private final DecisionEngine decisionEngine;
    private final ChatInvoker chatInvoker;

    public AgentPipeline(ProviderService providerService,
                         RuntimeConfigService runtimeConfigService,
                         GuardrailService guardrailService,
                         KnowledgeRetriever retriever,
                         PromptAssembler promptAssembler,
                         DecisionEngine decisionEngine,
                         ChatInvoker chatInvoker) {
        this.providerService = providerService;
        this.runtimeConfigService = runtimeConfigService;
        this.guardrailService = guardrailService;
        this.retriever = retriever;
        this.promptAssembler = promptAssembler;
        this.decisionEngine = decisionEngine;
        this.chatInvoker = chatInvoker;
    }

    public AiResponse run(AiRequest req) {
        long start = System.currentTimeMillis();

        EffectiveConfig base = runtimeConfigService.effectiveBase(req.tenantId());
        EffectiveConfig eff = ConfigMerger.applyOverrides(base, req.overrides());
        AiProvider provider = providerService.resolve(eff.providerId());

        String buyerText = req.lastBuyerText();
        GuardrailVerdict verdict = guardrailService.evaluate(buyerText);

        // 高风险：直接转人工，不生成回复
        if (verdict.highRisk()) {
            return new AiResponse(null, null, verdict.intent(), 0.0, List.of(),
                    true, "HIGH", DecisionEngine.HANDOFF,
                    System.currentTimeMillis() - start, TokenUsage.empty(), List.of(), null);
        }

        List<Source> sources = retriever.retrieve(buyerText, eff.rag());
        String system = promptAssembler.system(eff, req, sources);

        List<ChatMessage> messages = new ArrayList<>();
        messages.add(ChatMessage.system(system));
        for (CanonicalMessage m : req.messages()) {
            if (m.role() == MessageRole.BUYER) messages.add(ChatMessage.user(m.content()));
            else if (m.role() == MessageRole.AGENT || m.role() == MessageRole.AI)
                messages.add(ChatMessage.assistant(m.content()));
        }
        if (messages.size() == 1) {
            messages.add(ChatMessage.user(buyerText));
        }

        ToolTraceRecorder recorder = new ToolTraceRecorder();
        boolean locked = req.overrides() != null && Boolean.TRUE.equals(req.overrides().toolsLocked());
        List<Object> tools = List.of(new EcomTools(recorder, req.sim(), locked));

        ChatResult result = chatInvoker.invoke(
                new ChatInvocation(provider, eff.model(), eff.generation(), messages, tools));

        List<String> forbidden = guardrailService.forbiddenHits(result.text());
        double confidence = baseConfidence(sources, forbidden);
        String risk = forbidden.isEmpty() ? "LOW" : "MEDIUM";
        // 禁词已由 baseConfidence 降到 0.2，decide 在任何渠道都只会给 DRAFT，故无需额外分支
        String decision = decisionEngine.decide(verdict, confidence, req.channel());

        return new AiResponse(
                result.text(), null, verdict.intent(), confidence, sources,
                DecisionEngine.HANDOFF.equals(decision), risk, decision,
                System.currentTimeMillis() - start, result.usage(),
                recorder.traces(), system);
    }

    /** Phase A 经验置信度：命中知识 + 无禁词 → 高；缺知识 → 中；命中禁词 → 低。 */
    private double baseConfidence(List<Source> sources, List<String> forbidden) {
        if (!forbidden.isEmpty()) return 0.2;
        if (sources != null && !sources.isEmpty()) return 0.85;
        return 0.55;
    }
}
```

- [ ] **Step 3: 写 `OutboundGuardTest`**

```java
package com.joker.aibrain.sandbox;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class OutboundGuardTest {
    private final OutboundGuard guard = new OutboundGuard();

    @Test
    void 沙盒禁止外发() {
        assertThrows(SandboxViolationException.class, () -> guard.assertAllowed(true));
    }

    @Test
    void 非沙盒允许外发() {
        assertDoesNotThrow(() -> guard.assertAllowed(false));
    }
}
```

- [ ] **Step 4: 写 `AgentPipelineTest`**

```java
package com.joker.aibrain.agent;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.joker.aibrain.canonical.AiRequest;
import com.joker.aibrain.canonical.AiResponse;
import com.joker.aibrain.canonical.CanonicalMessage;
import com.joker.aibrain.canonical.Channel;
import com.joker.aibrain.canonical.MessageRole;
import com.joker.aibrain.canonical.Overrides;
import com.joker.aibrain.canonical.SimContext;
import com.joker.aibrain.chat.FakeChatInvoker;
import com.joker.aibrain.guard.GuardrailService;
import com.joker.aibrain.provider.AiProvider;
import com.joker.aibrain.provider.AiProviderRepository;
import com.joker.aibrain.provider.ProviderService;
import com.joker.aibrain.rag.InMemoryKnowledgeRetriever;
import com.joker.aibrain.rag.KnowledgeChunk;
import com.joker.aibrain.runtime.RuntimeConfigService;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentPipelineTest {

    private AiRequest req(String text, Channel ch) {
        return new AiRequest("default", ch, null, "shop1", "c1",
                List.of(CanonicalMessage.of(MessageRole.BUYER, text)),
                SimContext.empty(), Overrides.none(), true);
    }

    private AgentPipeline pipeline(FakeChatInvoker fake) {
        ProviderService ps = new ProviderService(new FixedRepo());
        RuntimeConfigService rcs = new RuntimeConfigService(tenant -> null, new ObjectMapper());
        return new AgentPipeline(ps, rcs, new GuardrailService(),
                new InMemoryKnowledgeRetriever(List.of(
                        new KnowledgeChunk("1", "faq", "发货", "付款后48小时内发货"))),
                new PromptAssembler(), new DecisionEngine(), fake);
    }

    @Test
    void 普通问题产出草稿与诊断() {
        FakeChatInvoker fake = new FakeChatInvoker("亲，付款后48小时内发货哦");
        AiResponse resp = pipeline(fake).run(req("什么时候发货", Channel.TAOBAO));
        assertEquals(DecisionEngine.DRAFT, resp.decision());
        assertFalse(resp.handoff());
        assertEquals("general", resp.intent());
        assertFalse(resp.sources().isEmpty());
        assertNotNull(resp.assembledPrompt());
        assertEquals(1, fake.invocations.size());
        assertEquals(30, resp.usage().totalTokens());
    }

    @Test
    void 高风险直接转人工不调用模型() {
        FakeChatInvoker fake = new FakeChatInvoker("x");
        AiResponse resp = pipeline(fake).run(req("我要退款", Channel.NATIVE));
        assertTrue(resp.handoff());
        assertEquals(DecisionEngine.HANDOFF, resp.decision());
        assertEquals(0, fake.invocations.size());
    }

    static class FixedRepo implements AiProviderRepository {
        @Override public List<AiProvider> listEnabled() {
            AiProvider p = new AiProvider();
            p.setId(1L); p.setStatus(1);
            p.setBaseUrl("http://localhost"); p.setApiKey("k"); p.setTextModel("m");
            return List.of(p);
        }
        @Override public AiProvider byId(Long id) { return listEnabled().get(0); }
    }
}
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest='OutboundGuardTest,AgentPipelineTest'`
Expected: `Tests run: 2+2, Failures: 0`。

---

### Task 13: 沙盒会话持久化

**Files:**
- Create: `src/main/java/com/joker/aibrain/sandbox/SandboxSession.java`
- Create: `src/main/java/com/joker/aibrain/sandbox/SandboxMessage.java`
- Create: `src/main/java/com/joker/aibrain/sandbox/SandboxSessionMapper.java`
- Create: `src/main/java/com/joker/aibrain/sandbox/SandboxMessageMapper.java`
- Create: `src/main/java/com/joker/aibrain/sandbox/SandboxStore.java`
- Create: `src/main/java/com/joker/aibrain/sandbox/MyBatisSandboxStore.java`
- Test: `src/test/java/com/joker/aibrain/sandbox/FakeSandboxStore.java`

**Interfaces:**
- Produces:
  - `class SandboxSession`（`@Data`）：`Long id, String tenantId, String title, Integer isTest`
  - `class SandboxMessage`（`@Data`）：`Long id, Long sessionId, String role, String content, String metaJson`
  - `interface SandboxStore { SandboxSession create(String tenantId, String title); void appendMessage(Long sessionId, String role, String content); List<SandboxMessage> messages(Long sessionId); void delete(Long sessionId); List<SandboxSession> list(String tenantId); }`

- [ ] **Step 1: 写实体 + mapper**

```java
package com.joker.aibrain.sandbox;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_console_session")
public class SandboxSession {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String tenantId;
    private String title;
    private Integer isTest;
}
```
```java
package com.joker.aibrain.sandbox;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_console_message")
public class SandboxMessage {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long sessionId;
    private String role;
    private String content;
    private String metaJson;
}
```
```java
package com.joker.aibrain.sandbox;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface SandboxSessionMapper extends BaseMapper<SandboxSession> {
}
```
```java
package com.joker.aibrain.sandbox;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface SandboxMessageMapper extends BaseMapper<SandboxMessage> {
}
```

- [ ] **Step 2: 写 `SandboxStore` 接口 + MyBatis 实现**

```java
package com.joker.aibrain.sandbox;

import java.util.List;

public interface SandboxStore {
    SandboxSession create(String tenantId, String title);
    void appendMessage(Long sessionId, String role, String content);
    List<SandboxMessage> messages(Long sessionId);
    void delete(Long sessionId);
    List<SandboxSession> list(String tenantId);
}
```
```java
package com.joker.aibrain.sandbox;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class MyBatisSandboxStore implements SandboxStore {

    private final SandboxSessionMapper sessions;
    private final SandboxMessageMapper messages;

    public MyBatisSandboxStore(SandboxSessionMapper sessions, SandboxMessageMapper messages) {
        this.sessions = sessions;
        this.messages = messages;
    }

    @Override
    public SandboxSession create(String tenantId, String title) {
        SandboxSession s = new SandboxSession();
        s.setTenantId(tenantId == null ? "default" : tenantId);
        s.setTitle(title);
        s.setIsTest(1);
        sessions.insert(s);
        return s;
    }

    @Override
    public void appendMessage(Long sessionId, String role, String content) {
        SandboxMessage m = new SandboxMessage();
        m.setSessionId(sessionId);
        m.setRole(role);
        m.setContent(content);
        messages.insert(m);
    }

    @Override
    public List<SandboxMessage> messages(Long sessionId) {
        return messages.selectList(
                new QueryWrapper<SandboxMessage>().eq("session_id", sessionId).orderByAsc("id"));
    }

    @Override
    public void delete(Long sessionId) {
        messages.delete(new QueryWrapper<SandboxMessage>().eq("session_id", sessionId));
        sessions.deleteById(sessionId);
    }

    @Override
    public List<SandboxSession> list(String tenantId) {
        return sessions.selectList(
                new QueryWrapper<SandboxSession>().eq("tenant_id", tenantId).orderByDesc("id"));
    }
}
```

- [ ] **Step 3: 写测试夹具 `FakeSandboxStore`（供 Task 14 复用）**

```java
package com.joker.aibrain.sandbox;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class FakeSandboxStore implements SandboxStore {
    private long seq = 0;
    public final Map<Long, SandboxSession> sessionMap = new LinkedHashMap<>();
    public final Map<Long, List<SandboxMessage>> messageMap = new LinkedHashMap<>();

    @Override
    public SandboxSession create(String tenantId, String title) {
        SandboxSession s = new SandboxSession();
        s.setId(++seq);
        s.setTenantId(tenantId == null ? "default" : tenantId);
        s.setTitle(title);
        s.setIsTest(1);
        sessionMap.put(s.getId(), s);
        messageMap.put(s.getId(), new ArrayList<>());
        return s;
    }

    @Override
    public void appendMessage(Long sessionId, String role, String content) {
        SandboxMessage m = new SandboxMessage();
        m.setId((long) (messageMap.get(sessionId).size() + 1));
        m.setSessionId(sessionId);
        m.setRole(role);
        m.setContent(content);
        messageMap.get(sessionId).add(m);
    }

    @Override
    public List<SandboxMessage> messages(Long sessionId) {
        return messageMap.getOrDefault(sessionId, List.of());
    }

    @Override
    public void delete(Long sessionId) {
        sessionMap.remove(sessionId);
        messageMap.remove(sessionId);
    }

    @Override
    public List<SandboxSession> list(String tenantId) {
        return sessionMap.values().stream()
                .filter(s -> s.getTenantId().equals(tenantId))
                .sorted((a, b) -> Long.compare(b.getId(), a.getId()))
                .toList();
    }
}
```

- [ ] **Step 4: 编译验证**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q -DskipTests test-compile`
Expected: `BUILD SUCCESS`。

---

### Task 14: ConsoleService（meta + preview 编排 + 沙盒落库）

> 依赖 Task 15 的 `PresetRepository`（`ConsoleMetaService` 用它列预设）。执行顺序：**Task 13 → Task 15 → Task 14**。

**Files:**
- Create: `src/main/java/com/joker/aibrain/console/ConsoleMetaService.java`
- Create: `src/main/java/com/joker/aibrain/console/ConsoleService.java`
- Create: `src/main/java/com/joker/aibrain/console/PreviewRequest.java`
- Test: `src/test/java/com/joker/aibrain/console/ConsoleServiceTest.java`

**Interfaces:**
- Consumes: `AgentPipeline`、`SandboxStore`、`ProviderService`、`PresetRepository`、`GenerationParams`、`RagParams`
- Produces:
  - `ConsoleMetaService.meta()` → `Map<String,Object>`：`providers`（不含 apiKey）、`defaults`（generation/rag）、`presets` 列表
  - `record PreviewRequest(String tenantId, String sessionId, Channel channel, String text, SimContext sim, Overrides overrides)` — `sessionId` 为字符串，空表示新建
  - `ConsoleService.preview(PreviewRequest r)` → `Map<String,Object>`：`{ sessionId, isTest:true, response:AiResponse }`

- [ ] **Step 1: 写 `ConsoleMetaService`**

```java
package com.joker.aibrain.console;

import com.joker.aibrain.provider.AiProvider;
import com.joker.aibrain.provider.ProviderService;
import com.joker.aibrain.runtime.GenerationParams;
import com.joker.aibrain.runtime.RagParams;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ConsoleMetaService {

    private final ProviderService providerService;
    private final PresetRepository presetRepository;

    public ConsoleMetaService(ProviderService providerService, PresetRepository presetRepository) {
        this.providerService = providerService;
        this.presetRepository = presetRepository;
    }

    public Map<String, Object> meta() {
        List<Map<String, Object>> providers = new ArrayList<>();
        for (AiProvider p : providerService.listEnabled()) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", p.getId());
            m.put("name", p.getName());
            m.put("textModel", p.getTextModel());
            m.put("visionModel", p.getVisionModel());
            // 绝不回显 apiKey / baseUrl 中的敏感信息
            providers.add(m);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("providers", providers);
        out.put("presets", presetRepository.list("default"));
        out.put("defaults", Map.of(
                "generation", GenerationParams.defaults(),
                "rag", RagParams.defaults()));
        return out;
    }
}
```

- [ ] **Step 2: 写 `PreviewRequest`**

```java
package com.joker.aibrain.console;

import com.joker.aibrain.canonical.Channel;
import com.joker.aibrain.canonical.Overrides;
import com.joker.aibrain.canonical.SimContext;

public record PreviewRequest(
        String tenantId,
        String sessionId,
        Channel channel,
        String text,
        SimContext sim,
        Overrides overrides) {
}
```

- [ ] **Step 3: 写 `ConsoleService`**

```java
package com.joker.aibrain.console;

import com.joker.aibrain.agent.AgentPipeline;
import com.joker.aibrain.canonical.AiRequest;
import com.joker.aibrain.canonical.AiResponse;
import com.joker.aibrain.canonical.CanonicalMessage;
import com.joker.aibrain.canonical.MessageRole;
import com.joker.aibrain.sandbox.SandboxMessage;
import com.joker.aibrain.sandbox.SandboxSession;
import com.joker.aibrain.sandbox.SandboxStore;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ConsoleService {

    private final AgentPipeline pipeline;
    private final SandboxStore sandboxStore;

    public ConsoleService(AgentPipeline pipeline, SandboxStore sandboxStore) {
        this.pipeline = pipeline;
        this.sandboxStore = sandboxStore;
    }

    public Map<String, Object> preview(PreviewRequest r) {
        String tenant = (r.tenantId() == null || r.tenantId().isBlank()) ? "default" : r.tenantId();

        SandboxSession session;
        if (r.sessionId() == null || r.sessionId().isBlank()) {
            session = sandboxStore.create(tenant, "试打会话");
        } else {
            long id = Long.parseLong(r.sessionId());
            session = sandboxStore.list(tenant).stream()
                    .filter(s -> s.getId() == id).findFirst()
                    .orElseGet(() -> sandboxStore.create(tenant, "试打会话"));
        }

        sandboxStore.appendMessage(session.getId(), "buyer", r.text());

        // 载入本会话历史（多轮），使试打贴近真实上下文
        List<CanonicalMessage> history = new ArrayList<>();
        for (SandboxMessage m : sandboxStore.messages(session.getId())) {
            if ("buyer".equals(m.getRole())) {
                history.add(CanonicalMessage.of(MessageRole.BUYER, m.getContent()));
            } else if ("ai".equals(m.getRole())) {
                history.add(CanonicalMessage.of(MessageRole.AI, m.getContent()));
            }
        }
        if (history.isEmpty()) {
            history.add(CanonicalMessage.of(MessageRole.BUYER, r.text()));
        }

        AiRequest req = new AiRequest(
                tenant, r.channel(), null, r.sim() == null ? null : r.sim().shopId(), null,
                history, r.sim(), r.overrides(), true);

        AiResponse response = pipeline.run(req);

        // 沙盒：本服务不做任何外发；真实外发入口（后续 Sidecar/Gateway）必须过 OutboundGuard，
        // 试打路径运行时也无法外发（见 OutboundGuardTest）。
        sandboxStore.appendMessage(session.getId(), "ai", response.reply());

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("sessionId", String.valueOf(session.getId()));
        out.put("isTest", true);
        out.put("response", response);
        return out;
    }
}
```

- [ ] **Step 4: 写 `ConsoleServiceTest`**

```java
package com.joker.aibrain.console;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.joker.aibrain.agent.AgentPipeline;
import com.joker.aibrain.agent.DecisionEngine;
import com.joker.aibrain.agent.PromptAssembler;
import com.joker.aibrain.canonical.Channel;
import com.joker.aibrain.canonical.Overrides;
import com.joker.aibrain.canonical.SimContext;
import com.joker.aibrain.chat.FakeChatInvoker;
import com.joker.aibrain.guard.GuardrailService;
import com.joker.aibrain.provider.AiProvider;
import com.joker.aibrain.provider.AiProviderRepository;
import com.joker.aibrain.provider.ProviderService;
import com.joker.aibrain.rag.InMemoryKnowledgeRetriever;
import com.joker.aibrain.rag.KnowledgeChunk;
import com.joker.aibrain.runtime.RuntimeConfigService;
import com.joker.aibrain.sandbox.FakeSandboxStore;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ConsoleServiceTest {

    private ConsoleService service(FakeSandboxStore store, FakeChatInvoker fake) {
        ProviderService ps = new ProviderService(new FixedRepo());
        RuntimeConfigService rcs = new RuntimeConfigService(tenant -> null, new ObjectMapper());
        AgentPipeline pipeline = new AgentPipeline(ps, rcs, new GuardrailService(),
                new InMemoryKnowledgeRetriever(List.of(new KnowledgeChunk("1", "faq", "发货", "48小时内发货"))),
                new PromptAssembler(), new DecisionEngine(), fake);
        return new ConsoleService(pipeline, store);
    }

    @Test
    void 试打新建会话并落库且不外发() {
        FakeSandboxStore store = new FakeSandboxStore();
        FakeChatInvoker fake = new FakeChatInvoker("亲，48小时内发货哦");
        Map<String, Object> out = service(store, fake).preview(new PreviewRequest(
                "default", null, Channel.NATIVE, "什么时候发货", SimContext.empty(), Overrides.none()));
        assertEquals(true, out.get("isTest"));
        assertFalse(store.sessionMap.isEmpty());
        long sid = Long.parseLong((String) out.get("sessionId"));
        assertEquals(2, store.messages(sid).size());
        assertEquals("buyer", store.messages(sid).get(0).getRole());
        assertEquals("ai", store.messages(sid).get(1).getRole());
    }

    @Test
    void 复用已有会话继续追加消息() {
        FakeSandboxStore store = new FakeSandboxStore();
        FakeChatInvoker fake = new FakeChatInvoker("回复");
        ConsoleService svc = service(store, fake);
        Map<String, Object> first = svc.preview(new PreviewRequest(
                "default", null, Channel.NATIVE, "问题1", SimContext.empty(), Overrides.none()));
        String sid = (String) first.get("sessionId");
        svc.preview(new PreviewRequest(
                "default", sid, Channel.NATIVE, "问题2", SimContext.empty(), Overrides.none()));
        assertEquals(1, store.sessionMap.size());
        assertEquals(4, store.messages(Long.parseLong(sid)).size());
    }

    static class FixedRepo implements AiProviderRepository {
        @Override public List<AiProvider> listEnabled() {
            AiProvider p = new AiProvider();
            p.setId(1L); p.setStatus(1);
            p.setBaseUrl("http://localhost"); p.setApiKey("k"); p.setTextModel("m");
            return List.of(p);
        }
        @Override public AiProvider byId(Long id) { return listEnabled().get(0); }
    }
}
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=ConsoleServiceTest`
Expected: `Tests run: 2, Failures: 0`。

---

### Task 15: 预设 + 一键提升线上 + 审计

**Files:**
- Create: `src/main/java/com/joker/aibrain/console/AiConsolePreset.java`
- Create: `src/main/java/com/joker/aibrain/console/AiConsolePresetMapper.java`
- Create: `src/main/java/com/joker/aibrain/console/PresetRepository.java`
- Create: `src/main/java/com/joker/aibrain/console/MyBatisPresetRepository.java`
- Create: `src/main/java/com/joker/aibrain/console/PresetService.java`
- Create: `src/main/java/com/joker/aibrain/runtime/RuntimeConfigWriter.java`
- Create: `src/main/java/com/joker/aibrain/runtime/MyBatisRuntimeConfigWriter.java`
- Create: `src/main/java/com/joker/aibrain/audit/AuditLog.java`
- Create: `src/main/java/com/joker/aibrain/audit/AuditLogMapper.java`
- Create: `src/main/java/com/joker/aibrain/audit/AuditRepository.java`
- Create: `src/main/java/com/joker/aibrain/audit/MyBatisAuditRepository.java`
- Create: `src/main/java/com/joker/aibrain/audit/AuditService.java`
- Test: `src/test/java/com/joker/aibrain/console/PresetServiceTest.java`

**Interfaces:**
- Produces:
  - `interface PresetRepository { List<AiConsolePreset> list(String tenantId); AiConsolePreset byId(Long id); AiConsolePreset save(AiConsolePreset preset); void delete(Long id); }`
  - `interface RuntimeConfigWriter { void saveConfig(String tenantId, String configJson, Long sourcePresetId, String updatedBy); }`
  - `interface AuditRepository { void write(String action, String target, String detailJson, String operator); }`
  - `PresetService.promote(Long id, String operator) -> void`（写运行配置 + 审计）

- [ ] **Step 1: 写预设实体 + mapper + repository**

```java
package com.joker.aibrain.console;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_console_preset")
public class AiConsolePreset {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String tenantId;
    private String name;
    private String paramsJson;
    private String remark;
    private String createBy;
}
```
```java
package com.joker.aibrain.console;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AiConsolePresetMapper extends BaseMapper<AiConsolePreset> {
}
```
```java
package com.joker.aibrain.console;

import java.util.List;

public interface PresetRepository {
    List<AiConsolePreset> list(String tenantId);
    AiConsolePreset byId(Long id);
    AiConsolePreset save(AiConsolePreset preset);
    void delete(Long id);
}
```
```java
package com.joker.aibrain.console;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class MyBatisPresetRepository implements PresetRepository {

    private final AiConsolePresetMapper mapper;

    public MyBatisPresetRepository(AiConsolePresetMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public List<AiConsolePreset> list(String tenantId) {
        return mapper.selectList(
                new QueryWrapper<AiConsolePreset>().eq("tenant_id", tenantId).orderByDesc("id"));
    }

    @Override
    public AiConsolePreset byId(Long id) {
        return mapper.selectById(id);
    }

    @Override
    public AiConsolePreset save(AiConsolePreset preset) {
        AiConsolePreset existing = mapper.selectOne(new QueryWrapper<AiConsolePreset>()
                .eq("tenant_id", preset.getTenantId()).eq("name", preset.getName()).last("LIMIT 1"));
        if (existing == null) {
            mapper.insert(preset);
            return preset;
        }
        existing.setParamsJson(preset.getParamsJson());
        existing.setRemark(preset.getRemark());
        existing.setCreateBy(preset.getCreateBy());
        mapper.updateById(existing);
        return existing;
    }

    @Override
    public void delete(Long id) {
        mapper.deleteById(id);
    }
}
```

- [ ] **Step 2: 写运行配置写入 + 审计**

```java
package com.joker.aibrain.runtime;

public interface RuntimeConfigWriter {
    void saveConfig(String tenantId, String configJson, Long sourcePresetId, String updatedBy);
}
```
```java
package com.joker.aibrain.runtime;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.springframework.stereotype.Repository;

@Repository
public class MyBatisRuntimeConfigWriter implements RuntimeConfigWriter {

    private final RuntimeConfigMapper mapper;

    public MyBatisRuntimeConfigWriter(RuntimeConfigMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public void saveConfig(String tenantId, String configJson, Long sourcePresetId, String updatedBy) {
        String t = tenantId == null ? "default" : tenantId;
        AiRuntimeConfig existing = mapper.selectOne(
                new QueryWrapper<AiRuntimeConfig>().eq("tenant_id", t).last("LIMIT 1"));
        if (existing == null) {
            AiRuntimeConfig row = new AiRuntimeConfig();
            row.setTenantId(t);
            row.setConfigJson(configJson);
            row.setSourcePresetId(sourcePresetId);
            row.setUpdatedBy(updatedBy);
            mapper.insert(row);
        } else {
            existing.setConfigJson(configJson);
            existing.setSourcePresetId(sourcePresetId);
            existing.setUpdatedBy(updatedBy);
            mapper.updateById(existing);
        }
    }
}
```
```java
package com.joker.aibrain.audit;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_audit_log")
public class AuditLog {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String action;
    private String target;
    private String detailJson;
    private String operator;
}
```
```java
package com.joker.aibrain.audit;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AuditLogMapper extends BaseMapper<AuditLog> {
}
```
```java
package com.joker.aibrain.audit;

public interface AuditRepository {
    void write(String action, String target, String detailJson, String operator);
}
```
```java
package com.joker.aibrain.audit;

import org.springframework.stereotype.Repository;

@Repository
public class MyBatisAuditRepository implements AuditRepository {

    private final AuditLogMapper mapper;

    public MyBatisAuditRepository(AuditLogMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public void write(String action, String target, String detailJson, String operator) {
        AuditLog log = new AuditLog();
        log.setAction(action);
        log.setTarget(target);
        log.setDetailJson(detailJson);
        log.setOperator(operator);
        mapper.insert(log);
    }
}
```
```java
package com.joker.aibrain.audit;

import org.springframework.stereotype.Service;

@Service
public class AuditService {
    private final AuditRepository repository;

    public AuditService(AuditRepository repository) {
        this.repository = repository;
    }

    public void record(String action, String target, String detailJson, String operator) {
        repository.write(action, target, detailJson, operator);
    }
}
```

- [ ] **Step 3: 写 `PresetService`**

```java
package com.joker.aibrain.console;

import com.joker.aibrain.audit.AuditService;
import com.joker.aibrain.runtime.RuntimeConfigWriter;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class PresetService {

    private final PresetRepository presetRepository;
    private final RuntimeConfigWriter runtimeConfigWriter;
    private final AuditService auditService;

    public PresetService(PresetRepository presetRepository,
                         RuntimeConfigWriter runtimeConfigWriter,
                         AuditService auditService) {
        this.presetRepository = presetRepository;
        this.runtimeConfigWriter = runtimeConfigWriter;
        this.auditService = auditService;
    }

    public List<AiConsolePreset> list(String tenantId) {
        return presetRepository.list(tenantId == null ? "default" : tenantId);
    }

    public AiConsolePreset save(String tenantId, String name, String paramsJson, String remark, String operator) {
        AiConsolePreset p = new AiConsolePreset();
        p.setTenantId(tenantId == null ? "default" : tenantId);
        p.setName(name);
        p.setParamsJson(paramsJson);
        p.setRemark(remark);
        p.setCreateBy(operator);
        return presetRepository.save(p);
    }

    public void delete(Long id) {
        presetRepository.delete(id);
    }

    /** 一键提升：把预设参数写为线上运行配置，并留审计（同一事务，杜绝"改了却没记"）。 */
    @Transactional
    public void promote(Long id, String operator) {
        AiConsolePreset p = presetRepository.byId(id);
        if (p == null) {
            throw new IllegalArgumentException("预设不存在: " + id);
        }
        runtimeConfigWriter.saveConfig(p.getTenantId(), p.getParamsJson(), p.getId(), operator);
        auditService.record("preset.promote", "preset:" + id, p.getParamsJson(), operator);
    }
}
```

- [ ] **Step 4: 写 `PresetServiceTest`**

```java
package com.joker.aibrain.console;

import com.joker.aibrain.audit.AuditRepository;
import com.joker.aibrain.audit.AuditService;
import com.joker.aibrain.runtime.RuntimeConfigWriter;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PresetServiceTest {

    static class FakePresetRepo implements PresetRepository {
        final List<AiConsolePreset> presets = new ArrayList<>();
        long seq = 0;
        @Override public List<AiConsolePreset> list(String t) { return presets; }
        @Override public AiConsolePreset byId(Long id) {
            return presets.stream().filter(p -> p.getId().equals(id)).findFirst().orElse(null);
        }
        @Override public AiConsolePreset save(AiConsolePreset p) {
            AiConsolePreset existing = presets.stream()
                    .filter(x -> x.getTenantId().equals(p.getTenantId()) && x.getName().equals(p.getName()))
                    .findFirst().orElse(null);
            if (existing != null) {
                existing.setParamsJson(p.getParamsJson());
                return existing;
            }
            p.setId(++seq);
            presets.add(p);
            return p;
        }
        @Override public void delete(Long id) { presets.removeIf(p -> p.getId().equals(id)); }
    }

    static class RecordingWriter implements RuntimeConfigWriter {
        String tenant; String json; Long presetId; String operator;
        @Override public void saveConfig(String tenantId, String configJson, Long sourcePresetId, String updatedBy) {
            this.tenant = tenantId; this.json = configJson; this.presetId = sourcePresetId; this.operator = updatedBy;
        }
    }

    static class RecordingAudit implements AuditRepository {
        final List<String> actions = new ArrayList<>();
        @Override public void write(String action, String target, String detailJson, String operator) {
            actions.add(action);
        }
    }

    @Test
    void 保存同名预设原地更新() {
        FakePresetRepo repo = new FakePresetRepo();
        PresetService svc = new PresetService(repo, new RecordingWriter(), new AuditService(new RecordingAudit()));
        svc.save("default", "A", "{\"model\":\"m1\"}", null, "admin");
        svc.save("default", "A", "{\"model\":\"m2\"}", null, "admin");
        assertEquals(1, repo.presets.size());
        assertEquals("{\"model\":\"m2\"}", repo.presets.get(0).getParamsJson());
    }

    @Test
    void 提升写运行配置并留审计() {
        FakePresetRepo repo = new FakePresetRepo();
        RecordingWriter writer = new RecordingWriter();
        RecordingAudit audit = new RecordingAudit();
        PresetService svc = new PresetService(repo, writer, new AuditService(audit));
        AiConsolePreset p = svc.save("default", "A", "{\"model\":\"m1\"}", null, "admin");
        svc.promote(p.getId(), "admin");
        assertNotNull(writer.json);
        assertEquals("m1", writer.json.contains("m1") ? "m1" : writer.json);
        assertEquals(p.getId(), writer.presetId);
        assertEquals("admin", writer.operator);
        assertEquals(List.of("preset.promote"), audit.actions);
    }

    @Test
    void 提升不存在的预设报错() {
        PresetService svc = new PresetService(new FakePresetRepo(),
                new RecordingWriter(), new AuditService(new RecordingAudit()));
        assertThrows(IllegalArgumentException.class, () -> svc.promote(999L, "admin"));
    }
}
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=PresetServiceTest`
Expected: `Tests run: 3, Failures: 0`。

---

### Task 16: REST 控制器 + 控制台鉴权

**Files:**
- Create: `src/main/java/com/joker/aibrain/console/ConsoleController.java`
- Create: `src/main/java/com/joker/aibrain/console/SessionController.java`
- Create: `src/main/java/com/joker/aibrain/console/PresetController.java`
- Create: `src/main/java/com/joker/aibrain/console/PresetSaveRequest.java`
- Create: `src/main/java/com/joker/aibrain/console/ConsoleAuthInterceptor.java`
- Create: `src/main/java/com/joker/aibrain/console/WebConfig.java`
- Test: `src/test/java/com/joker/aibrain/console/ConsoleAuthInterceptorTest.java`

**Interfaces:**
- Produces:
  - `GET /console/meta` → `map`
  - `POST /console/preview` (body `PreviewRequest`) → `map`
  - `GET /console/session`；`GET /console/session/{id}`；`DELETE /console/session/{id}`
  - `GET /console/preset`；`POST /console/preset`（body `PresetSaveRequest`）；`DELETE /console/preset/{id}`；`POST /console/preset/{id}/promote`
  - `ConsoleAuthInterceptor`：校验请求头 `X-Console-Token`

- [ ] **Step 1: 写 `PresetSaveRequest` + `ConsoleController`**

```java
package com.joker.aibrain.console;

public record PresetSaveRequest(String tenantId, String name, String paramsJson, String remark) {
}
```
```java
package com.joker.aibrain.console;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/console")
public class ConsoleController {

    private final ConsoleMetaService metaService;
    private final ConsoleService consoleService;

    public ConsoleController(ConsoleMetaService metaService, ConsoleService consoleService) {
        this.metaService = metaService;
        this.consoleService = consoleService;
    }

    @GetMapping("/meta")
    public Map<String, Object> meta() {
        return metaService.meta();
    }

    @PostMapping("/preview")
    public Map<String, Object> preview(@RequestBody PreviewRequest request) {
        return consoleService.preview(request);
    }
}
```

- [ ] **Step 2: 写 `SessionController` + `PresetController`**

```java
package com.joker.aibrain.console;

import com.joker.aibrain.sandbox.SandboxMessage;
import com.joker.aibrain.sandbox.SandboxSession;
import com.joker.aibrain.sandbox.SandboxStore;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/console/session")
public class SessionController {

    private final SandboxStore store;

    public SessionController(SandboxStore store) {
        this.store = store;
    }

    @GetMapping
    public List<SandboxSession> list(@RequestParam(defaultValue = "default") String tenantId) {
        return store.list(tenantId);
    }

    @GetMapping("/{id}")
    public List<SandboxMessage> messages(@PathVariable Long id) {
        return store.messages(id);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        store.delete(id);
    }
}
```
```java
package com.joker.aibrain.console;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/console/preset")
public class PresetController {

    private final PresetService presetService;

    public PresetController(PresetService presetService) {
        this.presetService = presetService;
    }

    @GetMapping
    public List<AiConsolePreset> list(@RequestParam(defaultValue = "default") String tenantId) {
        return presetService.list(tenantId);
    }

    @PostMapping
    public AiConsolePreset save(@RequestBody PresetSaveRequest req) {
        return presetService.save(req.tenantId(), req.name(), req.paramsJson(), req.remark(), "console-admin");
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        presetService.delete(id);
    }

    @PostMapping("/{id}/promote")
    public void promote(@PathVariable Long id) {
        presetService.promote(id, "console-admin");
    }
}
```

- [ ] **Step 3: 写鉴权拦截器 + WebConfig**

```java
package com.joker.aibrain.console;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
public class ConsoleAuthInterceptor implements HandlerInterceptor {

    public static final String HEADER = "X-Console-Token";

    private final String token;

    public ConsoleAuthInterceptor(@Value("${ai.console.token:dev-token}") String token) {
        this.token = token;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String provided = request.getHeader(HEADER);
        if (token.equals(provided)) {
            return true;
        }
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        return false;
    }
}
```
```java
package com.joker.aibrain.console;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final ConsoleAuthInterceptor authInterceptor;

    public WebConfig(ConsoleAuthInterceptor authInterceptor) {
        this.authInterceptor = authInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(authInterceptor).addPathPatterns("/console/**");
    }
}
```

- [ ] **Step 4: 写 `ConsoleAuthInterceptorTest`**

```java
package com.joker.aibrain.console;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ConsoleAuthInterceptorTest {

    @Test
    void 正确token放行() {
        ConsoleAuthInterceptor i = new ConsoleAuthInterceptor("secret");
        MockHttpServletRequest req = new MockHttpServletRequest();
        req.addHeader(ConsoleAuthInterceptor.HEADER, "secret");
        assertTrue(i.preHandle(req, new MockHttpServletResponse(), new Object()));
    }

    @Test
    void 错误或缺失token返回401() {
        ConsoleAuthInterceptor i = new ConsoleAuthInterceptor("secret");
        MockHttpServletResponse resp = new MockHttpServletResponse();
        assertFalse(i.preHandle(new MockHttpServletRequest(), resp, new Object()));
        assertEquals(401, resp.getStatus());
    }
}
```

- [ ] **Step 5: 运行测试**

Run: `cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test -Dtest=ConsoleAuthInterceptorTest`
Expected: `Tests run: 2, Failures: 0`。

---

### Task 17: 收尾、全量测试与手动冒烟

**Files:**
- Create: `spzx-ai-brain/README.md`
- Modify: `spzx-parent/AGENTS.md`（在 `automation/` 之外新增一节，注明 `spzx-ai-brain` 独立工程、端口、库、启动方式）

**Interfaces:**
- Consumes: 全部
- Produces: 一个可启动、可试打、可提升预设的独立服务。

- [ ] **Step 1: 写 `README.md`**

````markdown
# spzx-ai-brain

AI 客服「AI 大脑」独立服务（Phase A）。Chatwoot 壳 / Channel Sidecar / canonical 中台为后续计划。

## 运行

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
# 依赖 MySQL 的 db_ai_brain（首次：mysql --defaults-extra-file=/tmp/spzx_my.cnf < src/main/resources/schema.sql）
mvn -q spring-boot:run
```

端口 `8600`。配置：`application.yml` + gitignore 的 `application-local.yml`（库口令 / 控制台 token）。

## 控制台 API（需请求头 `X-Console-Token`）

- `GET  /console/meta`
- `POST /console/preview`
- `GET  /console/session`、`GET|DELETE /console/session/{id}`
- `GET|POST /console/preset`、`DELETE /console/preset/{id}`、`POST /console/preset/{id}/promote`

## 边界

- Phase A 工具为只读 mock，真实 spzx Connector + pgvector RAG + 试打台 SPA 为后续计划。
- 试打全链路沙盒：不写 Chatwoot、不外发（`OutboundGuard` 硬拦）。
````

- [ ] **Step 2: 起真实 MySQL 后端并把 provider 插入一条真实记录**

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_ai_brain -e "
INSERT INTO ai_provider(name,base_url,api_key,text_model,status) VALUES
('deepseek','https://api.deepseek.com','<填真实key>','deepseek-chat',1)
ON DUPLICATE KEY UPDATE base_url=VALUES(base_url), text_model=VALUES(text_model);"
```
Expected: 插入/更新 1 行。**apiKey 由执行人从 spzx `kw_provider` 表读取填入，绝不写进仓库。**

同时播种 spec §6.5 要求的「保守 / 均衡 / 创意」三个生成参数预设：

```bash
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_ai_brain -e "
INSERT INTO ai_console_preset(tenant_id,name,params_json,remark,create_by) VALUES
('default','保守','{\"generation\":{\"temperature\":0.1,\"topP\":0.8,\"maxTokens\":800}}','低随机、稳','system'),
('default','均衡','{\"generation\":{\"temperature\":0.3,\"topP\":0.9,\"maxTokens\":1024}}','默认档','system'),
('default','创意','{\"generation\":{\"temperature\":0.9,\"topP\":0.95,\"maxTokens\":1500}}','高随机','system')
ON DUPLICATE KEY UPDATE params_json=VALUES(params_json), remark=VALUES(remark);"
```
Expected: 3 行。`params_json` 结构对应 `ConfigPayload`，提升线上后即生效（优先级：线上配置 > 代码默认值）。

- [ ] **Step 3: 启动服务**

```bash
cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q spring-boot:run
```
Expected: 日志出现 `Started AiBrainApplication`，端口 8600 监听。若启动报 MyBatis-Plus / Spring Boot 3.4 兼容错误，记录完整异常；回退方案：把 `mybatis-plus.version` 升到与 Boot 3.4 匹配的版本（≥3.5.9）或改用 `spring-boot-starter-jdbc` + `JdbcTemplate` 重写 repository 实现（接口不变，上层与测试不受影响）。

- [ ] **Step 4: curl 冒烟（另开终端）**

```bash
TOKEN=$(grep -A2 'ai:' /Users/qyk9527/ideaProject/spzx-ai-brain/src/main/resources/application-local.yml | grep token | awk '{print $2}')
curl -s -H "X-Console-Token: $TOKEN" http://localhost:8600/console/meta | python3 -m json.tool
curl -s -H "X-Console-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"tenantId":"default","channel":"NATIVE","text":"什么时候发货？","overrides":{}}' \
  http://localhost:8600/console/preview | python3 -m json.tool
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8600/console/meta
```
Expected: `/console/meta` 返回 provider 列表（**无 apiKey**）；`/console/preview` 返回 `response` 且 `isTest=true`、`sources` 非空、`decision` 为 `DRAFT`/`AUTO`；无 token 时返回 `401`。

- [ ] **Step 5: 沙盒外发短路实测（防御性验收）**

在 Task 12 `OutboundGuardTest` 已断言沙盒外发必被拦（`OutboundGuard.assertAllowed(true)` 抛 `SandboxViolationException`）。手工再验：
```bash
mysql --defaults-extra-file=/tmp/spzx_my.cnf db_ai_brain -e "SELECT COUNT(*) FROM ai_console_message;"
```
Expected: 试打后行数增长，但 **Chatwoot / 生产表零写入**（本服务根本不连 Chatwoot）。

- [ ] **Step 6: 全量测试 + 打包**

```bash
cd /Users/qyk9527/ideaProject/spzx-ai-brain && mvn -q test && mvn -q -DskipTests package
```
Expected: 全部测试通过；`target/spzx-ai-brain-1.0-SNAPSHOT.jar` 生成。

- [ ] **Step 7: 更新 `spzx-parent/AGENTS.md`**

在「## automation/」一节之后新增一段：

```markdown
## spzx-ai-brain（独立工程，AI 客服「AI 大脑」Phase A）

- 路径 `/Users/qyk9527/ideaProject/spzx-ai-brain`（spzx-parent 兄弟目录，独立 Maven 工程，Spring Boot 3.4.5 + Spring AI 1.0.x）。
- 端口 8600；库 `db_ai_brain`（MySQL 同实例）；口令/控制台 token 在 gitignore 的 `application-local.yml`。
- 构建：`export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"`，`mvn -q spring-boot:run`。
- 边界：Phase A 工具只读 mock；试打全链路沙盒、零外发（`OutboundGuard` 硬拦）。
- spec/plan：`docs/superpowers/{specs,plans}/2026-10-09-ai-*`。
```

- [ ] **Step 8: 提交（不做）**

用户明确不执行任何 git 提交。**本步骤跳过，仅在计划中留痕。**

---

## 执行顺序提醒

1. Task 1 → 2 → 4 → 3 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → **15 → 14** → 16 → 17。
2. Task 3 依赖 Task 4 的 `GenerationParams`/`RagParams`；Task 4 的 `ConfigMerger` 依赖 Task 3 的 `Overrides` —— 两者互为编译前提，**同一批内先写 record 再写逻辑**。
3. Task 14 的 `ConsoleMetaService` 依赖 Task 15 的 `PresetRepository`，故 **Task 15 先于 Task 14**。
4. 每个 Task 末尾的测试命令单独可跑；`mvn -q test` 只在 Task 17 全量跑一次。

## 未纳入本计划（后续独立计划）

- 工具接真实 spzx Connector（只读接口）与 pgvector RAG。
- 试打台 SPA（Vue 3 + Vite + Element Plus），对接本计划 `/console/*`。
- canonical 中台 + Helpdesk Gateway + Chatwoot Adapter（子系统 2）。
- Channel Sidecar 抖店/淘宝/拼多多渠道（子系统 3）。
- spzx Connector 只读接口（子系统 4）。

## 执行后修订（实际代码以此为准，台账见 `.superpowers/sdd/2026-10-09-ai-brain-phase-a/`）

执行期间接受的修正（本文件相应代码块已就地更新）：`schema.sql` 加 `USE db_ai_brain;`；mapper 全部 `@Mapper`（去掉 `@MapperScan`）；`PromptAssembler` 用 `Source.snippet()`；`EcomTools.orderKey` 锁定态不回退真实单号；`PresetService.promote` 加 `@Transactional`；`FakeSandboxStore.list` 改降序；`AgentPipeline` 去掉冗余的禁词决策分支。

**最终审查（final review）修复波（本文件代码块未逐一回改，以 `final-fix-report.md` 为准）**：
- `SpringAiChatInvoker`：改用 `ChatModel.call(Prompt)` + `ToolCallbacks`（core 依赖无 `spring-ai-client-chat`）；缓存 ChatModel（键含 id+baseUrl+model+apiKey）；工具循环 `internalToolExecutionEnabled(false)` + 有界 `ToolCallingManager`（上限 6 轮，超限去工具要最终回复）；HTTP 超时经 `OpenAiApi.Builder.restClientBuilder` 绑定（JDK HttpClient connect 10s / read 120s）。
- `ConsoleService`：转人工空回复存占位符 `（已转人工，无草稿）`；拼历史跳过空白行；非法 sessionId 按新会话处理（不再 500）。
- `application-local.yml`：控制台 token 用随机 32 hex（`application.yml` 的 `${AI_CONSOLE_TOKEN:dev-token}` 默认值仅为占位）。

交付结果：47→49 个单测全绿；真实模型冒烟通过（meta 无 apiKey、无 token 401、preview 真实回复、转人工后同会话可续打、`toolsLocked` 工具轮 `toolTrace` 非空）。**项目不属任何 git 仓库、且用户明令不提交，故无 commit；台账/报告是本计划唯一的持久记录（工作区保留）。**

