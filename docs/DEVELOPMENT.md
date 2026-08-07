# spzx-parent 开发文档

> 多平台电商运营后台 + 聚合支付中台
> Spring Boot 3.3.5 + Java 21 + MyBatis-Plus 3.5.9 单体应用

---

## 1. 技术栈总览

| 分类 | 技术 | 版本 |
|------|------|------|
| 语言 | Java | 21 |
| 框架 | Spring Boot | 3.3.5 |
| ORM | MyBatis-Plus | 3.5.9 |
| 数据库 | MySQL | 8.0 |
| 缓存 | Redis (Lettuce) | 7+ |
| 分布式锁 | Redisson | 3.37.0 |
| 消息队列 | RocketMQ | 2.3.3 (starter) |
| 搜索引擎 | Elasticsearch | 7.17.9 |
| OLAP | ClickHouse | 24.12 (JDBC 0.6.5) |
| 对象存储 | MinIO | 8.5.2 (SDK) |
| API 文档 | Knife4j (springdoc) | 4.1.0 |
| 日志 | Log4j2 | (Spring Boot 管理) |
| Excel | EasyExcel | 3.1.0 |
| JSON | fastjson | 2.0.21 |
| 工具库 | Hutool | 5.8.35 |

### 支付渠道 SDK

| 渠道 | SDK | 版本 |
|------|-----|------|
| 微信支付 | weixin-java-pay (WxJava) | 4.6.0 |
| 支付宝 | alipay-sdk-java | 4.39.79.ALL |
| PayPal | checkout-sdk / rest-api-sdk / paypal-core | 1.0.3 / 1.14.0 / 1.7.2 |
| Stripe | stripe-java | 24.2.0 |

---

## 2. 模块结构

```
spzx (parent)
├── spzx-model          实体/VO/DTO/枚举/事件/异常（无内部依赖）
├── spzx-common (pom)
│   ├── common-util     工具类/认证/MinIO/Redisson/支付SDK（→ spzx-model）
│   ├── common-service  Knife4j/校验/全局异常（→ common-util, spzx-model）
│   └── common-log      @Log AOP 切面 + Log4j2（→ common-util, spzx-model）
└── spzx-manager        控制器/服务/策略/消费者，Spring Boot 入口（→ 所有 common 模块）
```

**依赖规则**：`spzx-model` 不允许引用 `spzx-common`。

### 各模块职责

| 模块 | 职责 |
|------|------|
| `spzx-model` | 数据库实体、请求 DTO、响应 VO、领域对象、枚举、领域事件、异常 |
| `common-util` | `AuthContextUtil`（ThreadLocal 登录上下文）、`Constant`（白名单/常量）、`ExcelUtil`、MinIO/Redisson/支付 SDK 封装 |
| `common-service` | `Knife4jConfig`（API 文档）、`GlobalExceptionHandler`（全局异常）、`ServiceException`（业务异常）、Hibernate Validator |
| `common-log` | `@Log` 注解 + `LogAspect`（AOP 切面）、`@EnableLogAspect`（开关注解）、`AsyncOperLogService`（异步日志） |
| `spzx-manager` | REST 控制器、业务服务、支付策略、支付回调处理、PaymentFacade 编排层、状态机、MQ 生产者/消费者、定时任务 |

---

## 3. 环境准备

### 3.1 基础设施依赖

| 服务 | 端口 | 说明 |
|------|------|------|
| MySQL 8.0 | 3306 | 数据库 `db_spzx`，用户 `root/root123456` |
| Redis | 6379 | 无密码，Lettuce 单连接多路复用 |
| RocketMQ NameServer | 9876 | 支付事件投递 |
| Elasticsearch 7.17.9 | 9200 | 无密码，操作日志检索 |
| MinIO | 9000 | 文件存储，默认 `minioadmin/minioadmin` |
| ClickHouse 24.12 | 8123 (HTTP) / 9010 (TCP) | OLAP 分析，用户 `spzx/spzx123` |

### 3.2 环境变量覆盖

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `SPRING_DATASOURCE_USERNAME` | MySQL 用户名 | `root` |
| `SPRING_DATASOURCE_PASSWORD` | MySQL 密码 | `root123456` |
| `ROCKETMQ_NAME_SERVER` | RocketMQ 地址 | `localhost:9876` |

---

## 4. 构建与运行

### 4.1 Maven

本机未安装独立 Maven，使用 IntelliJ IDEA 内置 Maven：

```bash
export PATH="/Applications/IntelliJ IDEA.app/Contents/plugins/maven/lib/maven3/bin:$PATH"
```

### 4.2 编译

> `spzx-model` 必须先 `install`，因为 `spzx-manager` 依赖其 jar。

```bash
mvn install -pl spzx-model -DskipTests -q && mvn compile -pl spzx-manager -am
```

### 4.3 打包

```bash
mvn package -pl spzx-manager -am -DskipTests
# 产物：spzx-manager/target/spzx-manager.jar
```

### 4.4 启动

- 主类：`com.joker.spzx.manager.ManagerApplication`
- 端口：`8501`
- Profile：`dev`（`application.yml` 中 `spring.profiles.active=dev`）

```bash
java -jar spzx-manager/target/spzx-manager.jar
# 或 IDE 中直接运行 ManagerApplication
```

### 4.5 测试

- 无正式测试套件。
- `spzx-manager/src/test/.../EmailTest.java`：`@SpringBootTest`，需完整环境（MySQL/Redis/SMTP）。
- `spzx-model/src/test/.../GeneratorCode.java`：MyBatis-Plus 代码生成器，非测试。运行前需修改 `outPath`（硬编码 Windows 路径）和 `tables`。
- **不要运行 `mvn test`**：会拉起 Spring 上下文且依赖全部基础设施在线。

---

## 5. 配置详解

配置文件：`spzx-manager/src/main/resources/application-dev.yml`

### 5.1 Server (Tomcat)

| 配置 | 值 |
|------|-----|
| port | 8501 |
| connection-timeout | 20000ms |
| threads.max | 50 |
| threads.min-spare | 5 |
| max-connections | 2048 |
| accept-count | 50 |

### 5.2 MySQL (HikariCP)

```
url: jdbc:mysql://localhost:3306/db_spzx?characterEncoding=utf-8&useSSL=false&allowPublicKeyRetrieval=true
pool: maximum-pool-size=5, minimum-idle=2, max-lifetime=1800000ms
```

Hikari 预处理参数优化已开启（`cachePrepStmts`、`useServerPrepStmts`、`rewriteBatchedStatements`）。

### 5.3 Redis (Lettuce)

```
host: localhost, port: 6379, timeout: 3000ms, connect-timeout: 2000ms
```

### 5.4 Redisson（分布式锁）

```yaml
redisson:
  config: |
    singleServerConfig:
      address: "redis://localhost:6379"
```

### 5.5 RocketMQ

```yaml
rocketmq:
  name-server: ${ROCKETMQ_NAME_SERVER:localhost:9876}
  producer:
    group: pay_producer_group
    send-message-timeout: 3000
    retry-times-when-send-failed: 3
```

### 5.6 MinIO

```
endpoint: http://127.0.0.1:9000, bucket: spzx-manager
```

### 5.7 微信扫码登录

```
app-id: wxed9954c01bb89b47
mock-mode: true（本地开发模拟扫码，无需真实微信回调）
qr-ttl-seconds: 120, poll-interval-ms: 1500
```

### 5.8 Spring 特性

- `lazy-initialization: true`：Bean 懒加载
- `allow-bean-definition-overriding: true`：允许 Bean 定义覆盖
- 资源过滤：`spzx-manager` `filtering=true`，`${...}` 占位符会被 Maven 替换

---

## 6. 核心配置类

均位于 `spzx-manager/.../config/`：

| 类 | 职责 |
|----|------|
| `WebMvcConfiguration` | 注册 `LoginAuthInterceptor`（拦截 `/**`，排除白名单）；全局 CORS（`allowedOriginPatterns("*")`，`allowCredentials(true)`）；`@EnableScheduling` |
| `LoginAuthInterceptor` | 登录拦截器：白名单放行 → 取 header `token` → Redis 查 `user:login:{token}` → 续期 7 天 → `AuthContextUtil` 设入 `SysUser`；无 token 返回 HTTP 208 |
| `MybatisPlusConfig` | `OptimisticLockerInnerInterceptor` + `PaginationInnerInterceptor`（MySQL，maxLimit=500）；异步线程池（core=4, max=16, queue=200） |
| `RedisCacheConfig` | `RedisTemplate`（Jackson2Json + JavaTimeModule）；`RedisCacheManager` 默认 TTL 30min，按 cacheName 分级 TTL（menu:tree=2h, category:list=1h 等） |
| `AsyncConfig` | 异步线程池配置 |
| `ClickHouseConfig` | ClickHouse JDBC 数据源 |
| `ElasticsearchConfig` | ES RestHighLevelClient |
| `OkHttpConfig` / `HttpClientConfig` | HTTP 客户端 |
| `WxLoginProperties` | 微信登录配置属性绑定 |

### Knife4j（common-service）

- 分组 `admin-api`，匹配 `/admin/**`
- 访问地址：`http://localhost:8501/doc.html`
- 白名单已放行 `/doc.html`、`/swagger-ui.html`、`/webjars/**`、`/v3/**`

---

## 7. 登录与鉴权

### 流程

```
请求 → LoginAuthInterceptor.preHandle
  ├─ OPTIONS → 放行
  ├─ 命中白名单 → 放行
  ├─ 取 header "token"
  │   ├─ 空 → 返回 208 (LOGIN_AUTH)
  │   └─ Redis GET user:login:{token}
  │       ├─ 空 → 返回 208
  │       └─ 命中 → 续期 7 天 → AuthContextUtil.set(sysUser)
  └─ Controller → AuthContextUtil.get() 获取当前用户
```

`afterCompletion` 清除 ThreadLocal，防止内存泄漏。

### 白名单（`Constant.whiteList`）

- 登录/验证码：`/admin/system/index/login`、`/admin/system/index/genVarifyCode`
- 微信扫码：`/admin/system/index/wxLogin/{create,status,callback,bind,mockScan,mockConfirm}`
- 文件上传：`/admin/system/fileUpload`
- 静态资源：`/js/**`、`/css/**`、`/img/**`、`/fonts/**`、`/index.html`、`/favicon.ico`
- API 文档：`/doc.html`、`/swagger-ui.html`、`/webjars/**`、`/v3/**`、`/api-docs/**`、`/swagger-resources/**`
- 支付回调：`/api/pay/notify/**`（v1）、`/api/v2/pay/notify/**`（v2）

---

## 8. 日志

### Log4j2（`log4j2-spring.xml`）

已排除 Logback，使用 Log4j2 异步日志。

| Appender | 文件 | 滚动策略 | 保留 |
|----------|------|----------|------|
| Console | stdout | - | - |
| FileLog | `logs/spzx-manager.log` | 按天 + 100MB | 30 个 |
| ErrorLog | `logs/spzx-manager-error.log` | 按天 + 50MB | 30 个 |
| SqlLog | `logs/spzx-manager-sql.log` | 按天 + 100MB | 14 个 |

- `com.joker.spzx.manager.mapper` → info → SqlLog（additivity=false）
- `com.joker.spzx` → info → FileLog + ErrorLog
- `com.zaxxer.hikari` / `org.springframework` / `org.mybatis` / Redis → warn
- 根日志 AsyncRoot → Console

### 操作日志（common-log）

- `@Log` 注解标记需要记录的方法
- `@EnableLogAspect` 在主类开启切面
- `LogAspect` AOP 拦截，异步写入操作日志（`AsyncOperLogService`）

---

## 9. 支付中台架构

架构设计文档：`docs/PAYMENT_PLATFORM_ARCHITECTURE.md`

### 9.1 分层

```
PayV2Controller / NotifyController  →  PaymentFacade  →  PayStrategy
     (v2 API)                         (幂等+锁+状态机)     (渠道适配)
                                       ↓
                                    PayEventProducer → RocketMQ → 4个消费者
```

### 9.2 v1 vs v2

| 版本 | 调用链 | 说明 |
|------|--------|------|
| v1 | `PaymentController → PaymentServiceImpl → PayStrategy` | 保留，向后兼容 |
| v2 | `PayV2Controller → PaymentFacade → PayStrategy` | 新增幂等+锁+状态机+事件 |
| 回调 | `NotifyController` `/api/v2/pay/notify/{channel}` | 统一入口，已在白名单 |

### 9.3 关键类

| 类 | 路径 | 职责 |
|----|------|------|
| `PaymentFacade` | `facade/` | 统一编排：幂等→锁→状态机→策略→持久化→事件 |
| `PayStrategy` | `pay/strategy/` | 渠道策略接口（**永不改变**，新渠道实现即可自动注册） |
| `AbstractPayStrategy` | `pay/strategy/` | 模板方法基类 |
| `PayStrategyFactory` | `pay/strategy/` | Spring 自动收集所有 `@Component` 策略 |
| `ChannelNotifyHandler` | `pay/handler/` | 统一回调处理接口 |
| `NotifyHandlerFactory` | `pay/handler/` | 回调处理器工厂 |
| `IdempotentService` | `service/` | Redis SETNX 幂等 |
| `DistributedLockService` | `service/` | Redisson 分布式锁 |
| `PaymentStateMachine` | `domain/state/` | 支付状态机（9 状态） |
| `RefundStateMachine` | `domain/state/` | 退款状态机 |
| `PayEventProducer` | `mq/` | 8 个事件发送方法 |

### 9.4 支付渠道策略（27 个实现）

| 渠道 | 策略类 |
|------|--------|
| 微信 | `WechatJsapiPayStrategy`、`WechatNativePayStrategy`、`WechatAppPayStrategy`、`WechatH5PayStrategy`、`WechatMiniPayStrategy` |
| 支付宝 | `AlipayPagePayStrategy`、`AlipayWapPayStrategy`、`AlipayAppPayStrategy`、`AlipayScanPayStrategy`、`AlipayMiniPayStrategy` |
| 银联 | `UnionPayJsapiStrategy`、`UnionPayQrStrategy`、`UnionPayB2bStrategy` |
| PayPal | `PaypalCardStrategy`、`PaypalOrderStrategy` |
| Stripe | `StripeCardStrategy`、`StripeLinkStrategy` |
| 抖音 | `DouyinMiniStrategy`、`DouyinGuaranteeStrategy` |
| 京东 | `JdQuickStrategy`、`JdBaitiaoStrategy` |
| 拉卡拉 | `LakalaPosStrategy`、`LakalaQrStrategy` |
| 聚合 | `AggregateQrStrategy`、`AggregateH5Strategy` |

### 9.5 支付枚举

均在 `spzx-model/.../enums/pay/`：

| 枚举 | 说明 |
|------|------|
| `PayTypeEnum` | 25 种支付方式，9 渠道 |
| `PaymentStatusEnum` | 9 状态：UNPAID / PAYING / PAID / CLOSED / REFUNDING / PARTIAL_REFUNDED / REFUNDED / REFUND_FAILED / PAY_ERROR |
| `PayErrorCode` | 27 个错误码 + HTTP status |
| `ChannelEnum` | 9 渠道：WECHAT / ALIPAY / UNIONPAY / PAYPAL / STRIPE / DOUYIN / JD / LAKALA / AGGREGATE |
| `RefundStatusEnum` | 4 状态：REFUND_PENDING / REFUND_PROCESSING / REFUND_SUCCESS / REFUND_FAILED |

### 9.6 RocketMQ 事件

```
pay_topic:
  pay.created / pay.success / pay.failed / pay.closed / refund.requested / refund.success

pay_notify_topic:
  notify.pay / notify.refund

消费组:
  merchant_notify_group  — 商户回调通知
  accounting_group       — 会计记账
  risk_control_group     — 风控
  reconcile_prep_group   — 对账预备
```

### 9.7 新渠道接入步骤

1. `PayTypeEnum` 新增枚举值
2. 继承 `AbstractPayStrategy`（或渠道基类如 `AbstractWechatPayStrategy`、`AbstractAlipayPayStrategy`）
3. 实现 `doCreatePayment` / `doHandleNotify` / `doHandleRefundNotify`
4. 加 `@Component` — `PayStrategyFactory` 自动注册，无需改现有代码

---

## 10. 目录结构速查

### spzx-manager

```
com/joker/spzx/manager/
├── ManagerApplication.java        # 主入口
├── config/                        # 10 个配置类
├── controller/                    # 40 个 REST 控制器
├── service/                       # 41 个服务接口
│   └── impl/                      # 36 个服务实现
├── mapper/                        # 54 个 MyBatis-Plus Mapper
├── pay/                           # 支付中台
│   ├── config/                    # 11 个渠道配置
│   ├── strategy/                  # 策略接口 + 抽象基类 + 工厂
│   │   └── impl/                  # 27 个渠道策略实现
│   └── handler/                   # 回调处理接口 + 工厂
│       └── impl/                  # 回调实现
├── facade/                        # PaymentFacade 编排层
├── domain/state/                  # 支付/退款状态机
├── mq/                            # 事件生产者 + 4 个消费者
├── helper/                        # MenuHelper 等辅助工具
├── task/                          # 定时任务
├── job/                           # 重试 Job
└── excel/                         # Excel 导出 BO
```

### spzx-model

```
com/joker/spzx/model/
├── entity/                        # 数据库实体（base/h5/oper/order/pay/product/system/user）
├── dto/                           # 请求 DTO（h5/mall/order/pay/product/system）
├── vo/                            # 响应 VO（common/h5/mall/order/pay/product/system）
│   └── common/                    # Result、ResultCodeEnum
├── domain/pay/                    # 领域对象（PaymentOrder、PayTradeRecord、RefundOrder）
├── enums/pay/                     # 支付枚举
├── event/pay/                     # 领域事件（6 个）
└── exception/                     # PayException
```

---

## 11. 其他

- 代码生成：`spzx-model/src/test/GeneratorCode.java`，运行前改 `outPath` 和 `tables`
- 索引优化 SQL：`spzx-manager/src/main/resources/sql/db_optimization_plan.sql`（执行前需审阅）
- 远景规划：`docs/ARCHITECTURE.md`（微服务蓝图，未落地）
- Mapper XML：`classpath*:/mapper/**/*.xml`
