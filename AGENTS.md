# AGENTS.md — spzx-parent

## 项目概览

多平台电商运营后台 + 聚合支付中台，Spring Boot 3.3.5 + Java 21 + MyBatis-Plus 3.5.9 单体应用。

## 构建命令

```bash
# 本机未安装 mvn，使用 IntelliJ IDEA 内置 Maven
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"

# 编译（spzx-model 必须先 install，因 spzx-manager 依赖其 jar）
mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am

# 打包
mvn package -pl spzx-manager -am -DskipTests

# 启动：主类 com.joker.spzx.manager.ManagerApplication，端口 8501，profile dev
```

## 测试

- 无正式测试套件。仅有 `spzx-manager/src/test/.../EmailTest.java`（`@SpringBootTest`，需完整环境）和 `spzx-model/src/test/.../GeneratorCode.java`（代码生成器，非测试）。
- 不要运行 `mvn test`：会拉起 Spring 上下文且依赖 MySQL/Redis/RocketMQ 全部在线。

**已知编译错误**（预先存在的 SDK 版本兼容问题，非本次引入）：
- `AbstractWechatPayStrategy:49` — WxJava 4.6.0 `WxPayRefundNotifyV3Result.DecryptNotifyResult` 无 `getStatus()` 方法
- `PaypalOrderStrategy:45` — PayPal `checkout-sdk` 1.0.3 `OrdersCreateRequest.execute()` 签名不匹配
- `StripeCardStrategy:46` — Stripe 24.2.0 API 差异

## 模块边界

| 模块 | 职责 | 依赖方向 |
|------|------|----------|
| `spzx-model` | 实体/VO/DTO/枚举/事件/异常 | 无内部依赖 |
| `spzx-common/common-util` | 工具类、认证、MinIO、Redisson、支付 SDK | → spzx-model |
| `spzx-common/common-service` | Knife4j、校验、全局异常 | → common-util, spzx-model |
| `spzx-common/common-log` | @Log AOP 切面（Log4j2） | → common-util, spzx-model |
| `spzx-manager` | 控制器/服务/策略/消费者，Spring Boot 入口 | → 所有 common 模块 |

不要在 `spzx-model` 中引用 `spzx-common`。

## 支付中台架构（v2，正在建设中）

架构设计文档：`docs/PAYMENT_PLATFORM_ARCHITECTURE.md`

### 分层

```
PayV2Controller / NotifyController  →  PaymentFacade  →  PayStrategy
     (v2 API)                         (幂等+锁+状态机)     (渠道适配)
                                       ↓
                                    PayEventProducer → RocketMQ → 4个消费者
```

### 关键类

| 类 | 路径 | 职责 |
|---|---|---|
| `PaymentFacade` | `facade/` | 统一编排：幂等→锁→状态机→策略→持久化→事件 |
| `PayStrategy` | `pay/strategy/` | 渠道策略接口（**永不改变**，新渠道实现即可自动注册） |
| `PayStrategyFactory` | `pay/strategy/` | Spring 自动收集所有 `@Component` 策略 |
| `ChannelNotifyHandler` | `pay/handler/` | 统一回调处理接口 + `NotifyHandlerFactory` |
| `IdempotentService` | `service/` | Redis SETNX 幂等 |
| `DistributedLockService` | `service/` | Redisson 分布式锁 |
| `PaymentStateMachine` | `domain/state/` | 支付状态机（9状态） |
| `PayEventProducer` | `mq/` | 8个事件发送方法 |

### v1 vs v2

- v1: `PaymentController` → `PaymentServiceImpl` → `PayStrategy`（保留，向后兼容）
- v2: `PayV2Controller` → `PaymentFacade` → `PayStrategy`（新增幂等+锁+状态机+事件）
- 回调: `NotifyController` `/api/v2/pay/notify/{channel}` 统一入口

### 支付枚举

均在 `spzx-model/.../enums/pay/`：
- `PayTypeEnum`: 25种支付方式，9渠道
- `PaymentStatusEnum`: 9状态（UNPAID/PAYING/PAID/CLOSED/REFUNDING/PARTIAL_REFUNDED/REFUNDED/REFUND_FAILED/PAY_ERROR）
- `PayErrorCode`: 27个错误码 + HTTP status
- `ChannelEnum`: 9渠道

### RocketMQ 事件

```
pay_topic: pay.created / pay.success / pay.failed / pay.closed / refund.requested / refund.success
pay_notify_topic: notify.pay / notify.refund
消费组: merchant_notify_group, accounting_group, risk_control_group, reconcile_prep_group
```

### 新渠道接入

1. `PayTypeEnum` 新增枚举值
2. 继承 `AbstractPayStrategy`（或渠道基类）
3. 实现 `doCreatePayment` / `doHandleNotify` / `doHandleRefundNotify`
4. 加 `@Component` — `PayStrategyFactory` 自动注册，无需改现有代码

## 配置

- 配置文件: `application-dev.yml`（profile `dev`），端口 8501
- MySQL: `localhost:3306/db_spzx`，`root/root123456`（`SPRING_DATASOURCE_USERNAME/PASSWORD` 覆盖）
- Redis: `localhost:6379`，无密码
- RocketMQ: `localhost:9876`（`ROCKETMQ_NAME_SERVER` 覆盖）
- Redisson: 分布式锁，配置在 `redisson.config` YAML 节点
- 日志: Log4j2（`log4j2-spring.xml`，已排除 Logback）
- MyBatis-Plus: mapper XML 在 `classpath*:/mapper/**/*.xml`
- 资源过滤: `spzx-manager` `filtering=true`，`${...}` 占位符会被替换
- `lazy-initialization: true` + `allow-bean-definition-overriding: true`

## 回调白名单

`Constant.whiteList` 包含 `/api/pay/notify/**` 和 `/api/v2/pay/notify/**`，回调不走登录拦截。

## 基础设施

| 服务 | 端口 | 说明 |
|------|------|------|
| MySQL 8.0 | 3306 | `db_spzx`，`root/root123456` |
| Redis | 6379 | 无密码 |
| RocketMQ | 9876 | `ROCKETMQ_NAME_SERVER` 覆盖 |
| ES 7.17.9 | 9200 | 无密码 |
| MinIO | 9000 | `minioadmin/minioadmin` |
| ClickHouse 24.12 | 8123 / 9010 | `spzx/spzx123` |

均宿主机本地运行，不在容器中。

## 安全

- `application-dev.yml` 邮箱密码、微信 AppSecret 明文，生产用环境变量覆盖
- ClickHouse 有密码 `spzx/spzx123`，ES 无密码，仅限本地开发

## 其他

- 开发文档: `docs/DEVELOPMENT.md`
- 代码生成: `spzx-model/src/test/GeneratorCode.java`，运行前改 `outPath`（硬编码 Windows 路径）和 `tables`
- 索引优化: `spzx-manager/src/main/resources/sql/db_optimization_plan.sql`（执行前需审阅）
- 远景规划: `docs/ARCHITECTURE.md`（微服务蓝图，未落地）
