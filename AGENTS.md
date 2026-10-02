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

- `spzx-manager` 下 17 个测试类，**除 `EmailTest` 外全是纯 JUnit 单测**（不联网、不拉 Spring 上下文，覆盖 expense/kw/videogen/ingest/platform/promo 等）。单跑：
  `mvn test -pl spzx-manager -Dtest=AlipayBillCsvParserTest`
- `EmailTest` 是 `@SpringBootTest`，需 MySQL/Redis 在线；**裸 `mvn test` 会带上它**——环境不全必挂，单测一律用 `-Dtest=` 指定。
- `spzx-model/src/test/java/com/joker/GeneratorCode.java` 是 MyBatis-Plus 代码生成器（非测试），outPath/tables 硬编码旧机器，勿直接跑。
- **改 `spzx-model`（实体/VO）后必须完整重启后端**：devtools 热重启只重载 `target/classes`，`spzx-model` 以 jar 进 classpath，加字段会当场 `NoSuchMethodError`（先 `mvn install -pl spzx-model` 再重启）。
- 断言与实测矛盾时先 `hexdump` 字面量：`2026-09-01` 与 `2026/09/01` 在终端里看着一模一样，但 `LocalDate.parse` 只认后者——「测试不合逻辑地通过」九成是渲染骗眼，不是构建骗人。

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
- `spring.config.import: optional:classpath:application-local.yml` — 本地覆盖文件已 gitignore，**密钥/凭据放这里，勿提交**。
- 微信扫码登录 `wx.login.mock-mode: true`：dev 登录走 mock（白名单含 mockScan/mockConfirm），无需真实微信回调。
- MinIO `127.0.0.1:9000`（minioadmin/minioadmin），bucket `spzx-manager`。
- `spzx-manager` 资源 `filtering=true`：resources 里的 `${...}` 会被 Maven 构建期替换，勿把运行期占位符写进 yml。
- ES / ClickHouse：仅 pom 引入依赖，**无任何配置与代码引用，未启用**（yml 的 `app.enable-infra` 开关也无代码绑定）；**没有 RocketMQ**（依赖都没有）。
- dev 开了 `spring.main.lazy-initialization: true`：缺 bean / 配置错误会延迟到首次调用才爆，别只看启动日志判断健康。**`@Scheduled` 任务类必须加 `@Lazy(false)`**，否则 bean 永不实例化、任务永不调度（`OrderStatisticsTask`/`QrLoginTicketCleanTask` 就没加）。
- `task-progress.config-path`、`visual.python-bin/script-dir` 硬编码本机绝对路径指向 `automation/`，仓库搬家即失效；`visual.script-dir` 仍指向 sourcing 根，但 `assess_visual.py` 已归档到 `_archive_20260906/`——主图质量分重算目前找不到脚本。
- 根 pom 的 `<spring-boot.version>3.4.0</spring-boot.version>` 是**死属性**（无任何引用），实际生效的是 parent 3.3.5；升级版本改 parent 那行，勿被它误导。

## 登录拦截白名单

`common-util/.../utils/Constant.java` 的 `whiteList`：登录/微信 mock 路径、静态资源、swagger（`/doc.html`、`/v3/**`）。要放行新路径改这里，勿在拦截器里硬编码。

## 业务域（service/ 包）

| 包 | 用途 |
|----|------|
| `expense` | 对账管理：支付宝 CSV 幂等导入、打标规则引擎、月末关账 |
| `ingest` | 采集契约/新鲜度：`ingest_dataset` 判据 + 过期告警写 `sync_alert`（调度在系统 cron / LaunchAgent，后端只判定） |
| `kw` | AI 选词推广：引擎凭据在 DB `kw_provider` 表 + `application-local.yml`；`KwAutoRunTask` 默认关闭 |
| `platform` | 平台/店铺/能力只读注册表（`PlatformRegistryService`），P0 直查库不缓存 |
| `promo` | 推广日报：主路是 `automation/tb-auto/collect_alimama_promo.py` 直连万相台报表接口采集（LaunchAgent 每日 22:00）；`/admin/promo/import` 的 CSV 导入是兜底路，列名映射存 DB `promo_import_map`（当数据不当代码，全部 `verified=0` 未跟真实导出对过）；看板读接口 `/admin/promo/report/{summary,trend,plans,items,facetCounts}` 纯只读（前端 运营 > 推广日报）；比率一律用汇总后的分子分母重算，分母为 0 出 NULL 不出 0 |
| `videogen` | 火山方舟 Seedance 视频生成（`ArkVideoClient` + `VideoPricing` 计费护栏 + 启动对账 `VideoGenStartupReconciler`） |
| （无 `novel` 子包） | 小说/番茄逻辑在 service/ 顶层：`NovelService`、`NovelChapterService`、`FanqiePublishService` |

平台级业务细节/运营红线见全局 `~/.config/opencode/AGENTS.md`。

## 文档 / 杂项

- `docs/DEVELOPMENT.md`（开发文档）；`docs/ARCHITECTURE.md`（微服务蓝图，未落地）
- `docs/superpowers/`：功能交付台账（`specs/`+`plans/`+`audits/`）。2026-09-30 两份 PDD 设计（`pdd-wearable-nail-distribution`、`pdd-1688-product-binding`）**状态待评审、后端/前端未落地**，别按文档找 Java 代码。
- `spzx-manager/src/main/resources/sql/db_optimization_plan.sql`：索引优化方案（执行前审阅）
- 远程：GitHub `qyongkai9527/spzx-parent`

## automation/ — Python 电商自动化生态（sourcing/tb-auto/fanqie-publish 于 2026-09-23 从 `~/` 迁入；pdd-auto 2026-09-30 新建）

Playwright async + CDP。Python 3.9，统一 `automation/venv/bin/python`。**Chrome 风控红线 / CDP 端口分工 / cron / 小说发布闭环见全局 `~/.config/opencode/AGENTS.md`；逐目录坑位见 `automation/{sourcing,tb-auto,pdd-auto}/AGENTS.md`。**

| 子目录 | 用途 | CDP |
|---|---|---|
| `automation/sourcing/` | 1688 选品/归类调价/抖店直建 | 9223 |
| `automation/tb-auto/` | 1688→淘宝铺货/巡检/小说章节导入 | 9222 |
| `automation/fanqie-publish/` | 番茄小说自动发布（常驻 publish_auto.py，每日 12:00 发 8 章） | 9223 |
| `automation/pdd-auto/` | 淘宝穿戴甲→拼多多铺货（1688 直铺，`run_pdd_1688.sh` 循环） | 9224（发布，窗口模式）；采集复用 9222 |

- pdd-auto 是**第四条线**：CDP 9224 独立 profile，提交类必须窗口模式（PDD 发布入口是 `/goods/category` 不是 `/goods/publish`）；主图须缩到 1080px 否则商详校验静默拦截。细节见 `automation/pdd-auto/AGENTS.md`。
- 数据/缓存/登录态（chrome-profile*、*.jsonl、novel_batches、xlsx/mp4 等）已 gitignore，勿提交
- 代码中出现 `/Users/qyk9527/sourcing|tb-auto|fanqie-publish` 旧路径 = bug（yml/@Value 曾漏改 10 处，2026-09-24 已全部修复）
