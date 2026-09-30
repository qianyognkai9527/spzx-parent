# AGENTS.md — spzx-parent

多平台电商运营后台（Spring Boot 3.3.5 + Java 21 + MyBatis-Plus 3.5.9 单体）。「聚合支付中台」**只有设计稿、未落地**：`docs/PAYMENT_PLATFORM_ARCHITECTURE.md` 里的 PaymentFacade / PayV2Controller / PayStrategy / 状态机 / RocketMQ 事件等类**在代码中均不存在**，勿按文档找代码。

## 构建命令

```bash
# 本机未安装 mvn，用 IDEA 内置 Maven
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"

# 编译（spzx-manager 依赖 spzx-model jar，必须先 install）
mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am

# 打包 / 运行（主类 com.joker.spzx.manager.ManagerApplication，端口 8501，profile dev）
mvn package -pl spzx-manager -am -DskipTests
mvn spring-boot:run -pl spzx-manager
```

**无 CI、无 mvnw、无 lint/format 工具链**——验证只能本地跑：`mvn compile` + `mvn test -Dtest=…`。

## 测试

- 纯 JUnit 单测（不联网、不拉 Spring 上下文）：`AlipayBillCsvParserTest`、`VideoPromptParseTest`、`VideoJsonUtilTest`、`ArkVideoClientTest`。单跑：
  `mvn test -pl spzx-manager -Dtest=AlipayBillCsvParserTest`
- `EmailTest` 是 `@SpringBootTest`，需 MySQL/Redis 在线；**裸 `mvn test` 会带上它**——环境不全必挂，单测一律用 `-Dtest=` 指定。
- `spzx-model/src/test/java/com/joker/GeneratorCode.java` 是 MyBatis-Plus 代码生成器（非测试），outPath/tables 硬编码旧机器，勿直接跑。

## 模块边界

| 模块 | 内容 |
|------|------|
| `spzx-model` | 实体/VO/DTO/枚举（无内部依赖，勿引 spzx-common） |
| `spzx-common/common-util` | 工具类、`Constant`（登录白名单） |
| `spzx-common/common-service` | Knife4j 配置、全局异常 |
| `spzx-common/common-log` | `@Log` 注解 + AOP 切面（Log4j2 starter 也在此） |
| `spzx-manager` | controller/service/mapper，唯一 Spring Boot 入口 |

## 配置要点（`application-dev.yml`）

- MySQL `localhost:3306/db_spzx`（root/root123456）、Redis `localhost:6379`（无密码）——宿主机直装，**机器重启后不自启**。
- `spring.config.import: optional:application-local.yml` — 本地覆盖文件已 gitignore，**密钥/凭据放这里，勿提交**。
- 微信扫码登录 `wx.login.mock-mode: true`：dev 登录走 mock（白名单含 mockScan/mockConfirm），无需真实微信回调。
- MinIO `127.0.0.1:9000`（minioadmin/minioadmin），bucket `spzx-manager`。
- `spzx-manager` 资源 `filtering=true`：resources 里的 `${...}` 会被 Maven 构建期替换，勿把运行期占位符写进 yml。
- ES / ClickHouse：仅 pom 引入依赖，**无任何配置与代码引用，未启用**（yml 的 `app.enable-infra` 开关也无代码绑定）；**没有 RocketMQ**（依赖都没有）。
- dev 开了 `spring.main.lazy-initialization: true`：缺 bean / 配置错误会延迟到首次调用才爆，别只看启动日志判断健康。
- `task-progress.config-path`、`visual.python-bin/script-dir` 硬编码本机绝对路径指向 `automation/`，仓库搬家即失效。
- 根 pom 的 `<spring-boot.version>3.4.0</spring-boot.version>` 是**死属性**（无任何引用），实际生效的是 parent 3.3.5；升级版本改 parent 那行，勿被它误导。

## 登录拦截白名单

`common-util/.../utils/Constant.java` 的 `whiteList`：登录/微信 mock 路径、静态资源、swagger（`/doc.html`、`/v3/**`）。要放行新路径改这里，勿在拦截器里硬编码。

## 业务域（service/ 包）

| 包 | 用途 |
|----|------|
| `expense` | 对账管理：支付宝 CSV 幂等导入（`AlipayBillCsvParser`） |
| `kw` | AI 选词推广：引擎凭据在 DB `kw_provider` 表 + `application-local.yml` |
| `videogen` | 火山方舟 Seedance 视频生成（`ArkVideoClient` + 启动对账 `VideoGenStartupReconciler`） |
| （无 `novel` 子包） | 小说/番茄逻辑在 service/ 顶层：`NovelService`、`NovelChapterService`、`FanqiePublishService` |

平台级业务细节/运营红线见全局 `~/.config/opencode/AGENTS.md`。

## 文档 / 杂项

- `docs/DEVELOPMENT.md`（开发文档）；`docs/ARCHITECTURE.md`（微服务蓝图，未落地）
- `docs/superpowers/`：功能交付台账
- `spzx-manager/src/main/resources/sql/db_optimization_plan.sql`：索引优化方案（执行前审阅）
- 远程：GitHub `qyongkai9527/spzx-parent`

## automation/ — Python 电商自动化生态（原 ~/sourcing、~/tb-auto、~/fanqie-publish，2026-09-23 迁入）

Playwright async + CDP。Python 3.9，统一 `automation/venv/bin/python`。**Chrome 风控红线 / CDP 端口分工 / cron / 小说发布闭环见全局 `~/.config/opencode/AGENTS.md`；逐目录坑位见 `automation/sourcing/AGENTS.md`、`automation/tb-auto/AGENTS.md`。**

| 子目录 | 用途 | CDP |
|---|---|---|
| `automation/sourcing/` | 1688 选品/归类调价/抖店直建 | 9223 |
| `automation/tb-auto/` | 1688→淘宝铺货/巡检/小说章节导入 | 9222 |
| `automation/fanqie-publish/` | 番茄小说自动发布（常驻 publish_auto.py，每日 12:00 发 8 章） | 9223 |

- 数据/缓存/登录态（chrome-profile*、*.jsonl、novel_batches、xlsx/mp4 等）已 gitignore，勿提交
- 代码中出现 `/Users/qyk9527/sourcing|tb-auto|fanqie-publish` 旧路径 = bug（yml/@Value 曾漏改 10 处，2026-09-24 已全部修复）
