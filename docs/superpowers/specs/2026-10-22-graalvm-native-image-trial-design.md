# GraalVM Native Image 试验（spzx-manager）· 设计

日期：2026-10-22
状态：已评审（对话内四节逐节确认）

## 1. 目标与边界

### 成功标准（三级）

| 级别 | 标准 |
|---|---|
| L1 完整启动 | native 二进制以 dev profile 完整启动。MySQL/Redis 在线（均开机自启）；MinIO 未启动 → 文件上传类接口不可用属预期，不算失败 |
| L2 核心链路真实可用 | mock 登录 + 看板 KPI / 任务进度等 **3-5 个只读接口**返回正确数据。MyBatis-Plus 查库、fastjson2 序列化真实跑通，不是只看进程不崩 |
| L3 量化对比 | 启动耗时、RSS 内存与 `java -jar` 基线（实测 282-310MB / 启动 4.4s）对比，产出数据 |

### 性能预期（诚实口径）

native image 的确定性收益是**启动时间**（预计 4.4s → 1s 上下）和**常驻内存**（预计 300MB → 100-150MB）。峰值吞吐不一定赢过热身后的 JIT——本应用低流量、机器 16G 内存超售，收益正落在前两项。

### 扩展性

本次交付物除了二进制，还包括一份**可复制配方**（pom profile 模板 + agent 采集步骤 + 坑位记录）。验证通过后**另起会话**扩展到 spzx-ai-brain（Spring Boot 3.4.5 + Spring AI，原生支持更弱，需单独评估，不混进本次范围）。

### 不做

- 现网启动方式的切换动作本身（数据出来好看了再决定，另议）
- easyexcel 导出、文件上传等重反射路径的完整回归
- 全接口回归测试

## 2. 环境现状（已实测）

- **GraalVM 已装**：Oracle GraalVM 21.0.7+8.1，位于 `/Users/qyk9527/Library/Java/JavaVirtualMachines/graalvm-jdk-21.0.7/Contents/Home`，`native-image` 可用（版本 21.0.7）
- Spring Boot 3.3.5 + Java 21：官方支持 AOT/Native Image 的组合
- 依赖风险面：MyBatis-Plus 3.5.9（40 个 mapper XML、145 个 model 类）、spring-boot-devtools、POI 5.2.5/easyexcel 4.0.3、fastjson 2.0.65、Knife4j 4.1.0、Hutool、log4j2（common-log）
- ES / ClickHouse：仅 pom 引入、代码零引用（AGENTS.md 已确认未启用），但 ServiceLoader 会扫到 ClickHouse JDBC 驱动
- 本机未装独立 mvn，用 IDEA 内置 Maven（仓库既有模式）

## 3. 方案选择

**采用方案 A：Spring Boot 官方 AOT 路线。**

- 用 spring-boot-starter-parent 自带的插件体系，在 `spzx-manager/pom.xml` 加默认不激活的 `native` profile（native-maven-plugin + process-aot）
- 用 **tracing agent**（GraalVM 自带）自动收集反射/代理/资源配置——不手写 reflect-config：拿现有 jar 起一次进程，踩若干接口，agent 落成 JSON
- Spring AOT 会把大量反射转成构建期代码生成，是官方正路；可重复构建；JVM 侧零影响

否决方案：

- **方案 B（手动 `native-image -jar` 裸编）**：不接 Maven、绕开 Spring AOT，配置全靠 agent+手补，不可维护。仅当 Maven 集成出诡异问题时兜底
- **方案 C（Docker 容器内构建）**：本机刻意不启动 Docker Desktop（省 1GB），且 macOS 上 native-image 本机可编，容器纯浪费

改动落点：**主仓新 profile**（用户选定）。试验完随时 `-Pnative` 触发，平时构建零影响。

## 4. 改动清单（全部默认不激活，JVM 构建零影响）

1. **`spzx-manager/pom.xml` 新增 `native` profile**：
   - `native-maven-plugin`（版本由 Boot parent 管理）：开 reachability metadata 仓库（`<metadataRepository><enabled>true</enabled></metadataRepository>`，自动拉 log4j2/mysql/lettuce 等官方元数据）
   - `spring-boot-maven-plugin` 加 `process-aot` 执行
2. **`spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager/`** 放 agent 收集的 4 类 JSON（reflect-config.json / resource-config.json / proxy-config.json / serialization-config.json 等）。对 JVM 构建完全惰性（只是资源文件），native-image 按 META-INF 约定自动拾取，无需额外 buildArgs
3. **devtools**：AOT 处理与 native 不兼容。构建时先带 `-Dspring.devtools.restart.enabled=false` 起步；若 agent 采集或构建仍报 RestartClassLoader 相关错，临时把该依赖 scope 改 `provided`（一行改动，验完回滚）
4. **不动 application-*.yml**；口令仍走 `SPRING_DATASOURCE_PASSWORD` 环境变量，不进仓库

## 5. 操作流程（五步）

1. **装 model jar**（既有模式）：`mvn install -pl spzx-model -DskipTests`
2. **agent 采集**：
   ```bash
   JAVA_HOME=<GraalVM> java -agentlib:native-image-agent=config-output-dir=spzx-manager/src/main/resources/META-INF/native-image/com.joker/spzx-manager -jar spzx-manager/target/spzx-manager.jar
   ```
   等启动完成后依次 curl：mock 登录、看板 KPI、任务进度等 **3-5 个只读接口**（顺手踩到 MP 的 LambdaQueryWrapper 路径），优雅停机——agent 自动写 JSON
3. **编译**：`JAVA_HOME=<GraalVM> mvn -Pnative -pl spzx-manager package -DskipTests`
   - 预计 5-15 分钟、峰值 6-8G 内存；选机器空闲时段，**绝不与其它 maven 并发**（16G 超售，既有规则）
   - 必要时加 `-Ob`（快速构建模式）换编译时间
4. **验证**：`SPRING_DATASOURCE_PASSWORD=... ./target/spzx-manager --spring.profiles.active=dev`，curl 同样几个接口；记录启动耗时 / RSS，与基线（282-310MB / 4.4s）对比成表
5. **留痕**：结果（成败、坑位、数据对比）按仓库惯例 `log_work.py` 记台账，本文档补「实测结果」章节

## 6. 风险与后备

| 风险 | 后备 |
|---|---|
| ClickHouse/ES 驱动类静态初始化在构建期报错（零引用但 ServiceLoader 会扫到） | 把这两个依赖挪进默认激活的 `infra` profile，native 构建时 `-P!infra` 关掉（Maven profile 做不了减法，这是结构性后备） |
| MyBatis-Plus lambda 序列化缺条目 | agent 采集时多踩几个走 wrapper 的接口；个别手补 JSON |
| knife4j/springdoc 启动崩 | 运行二进制时加 `-Dspringdoc.api-docs.enabled=false`，不影响成功标准 |
| fastjson2/POI 未踩到的类 | 本次 L2 标准不涉及；构建期报错才补 |
| 内存超售导致构建 OOM | 构建前确认无其它 maven/重负载；必要时 `-Ob` |

## 7. 验收方式

- L1：二进制启动日志出现 `Started ManagerApplication`（native 模式下无 devtools，无热重启属预期），进程稳定 60s 不退出
- L2：curl mock 登录拿 token → 带 token curl 3-5 个只读 GET，HTTP 200 且 JSON 结构正确（与 JVM 版同接口输出一致）
- L3：对比表归档进本文档「实测结果」章节

## 8. 实测结果

（待实施后回填）
