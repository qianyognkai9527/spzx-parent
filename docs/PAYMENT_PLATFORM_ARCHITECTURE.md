# 聚合支付中台架构设计 v1.0

> 基于 spzx-parent 现有框架演进，构建高扩展、高并发、高可用的支付中台

---

## 一、现状分析与差距

### 1.1 现有能力

| 维度 | 现状 | 评价 |
|------|------|------|
| 渠道抽象 | `PayStrategy` 接口 + `AbstractPayStrategy` 模板方法 + `PayStrategyFactory` 工厂 | ✅ 策略模式，扩展性好 |
| 渠道覆盖 | 9 渠道 25 支付方式，27 策略类 | ✅ 枚举完备 |
| SDK 集成 | 微信/支付宝/Stripe 完整，PayPal 仅下单，5 渠道桩实现 | ⚠️ 需补齐 |
| 订单持久化 | `payment_info` 表，但回调后**未更新状态** | ❌ 严重缺陷 |
| 幂等性 | **无任何幂等机制** | ❌ 重复回调会重复处理 |
| 异步/解耦 | **无 MQ、无 @Async、无定时对账** | ❌ 全同步阻塞 |
| 回调白名单 | `/api/pay/notify/**` **未加入** `Constant.whiteList` | ❌ 回调被拦截 |
| 状态机 | `PaymentStatusEnum` 6 状态，但**无状态流转逻辑** | ❌ 状态不可控 |
| 分库分表 | 无 | ❌ 单表瓶颈 |
| 分布式锁 | 无 | ❌ 并发下单风险 |
| 对账 | 无 | ❌ 资金安全无保障 |
| 监控告警 | 无支付专项监控 | ❌ 故障不可感知 |

### 1.2 核心差距总结

```
现有：策略模式骨架 + 部分SDK集成 + 单表存储
缺失：状态机 + 幂等 + 异步解耦 + 分布式锁 + 对账 + 分库分表 + 监控告警 + 多租户
```

---

## 二、目标架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        客户端 (商家系统)                              │
│         REST API 调用 / SDK 接入 / 回调接收                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                     API 接入层                                       │
│   Nginx/SLB → Spring Cloud Gateway → 鉴权/限流/灰度/路由              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                   支付中台 API 层                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────────┐ │
│  │ 下单 Controller│ │ 回调 Controller│ │ 查询 Controller│ │ 对账 Controller│ │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬───────┘ │
│         │               │               │               │           │
│  ┌──────▼───────────────▼───────────────▼───────────────▼───────┐  │
│  │              PaymentFacade (统一门面)                         │  │
│  │   幂等校验 → 分布式锁 → 状态机 → 策略分发 → 事件发布          │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
└─────────────────────────────┼─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                    领域服务层 (Domain)                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │OrderDomain│ │PayDomain │ │RefundDom │ │ChannelDom│ │RouteDom  ││
│  │ 订单聚合根 │ │ 支付聚合根│ │ 退款聚合根│ │ 渠道管理  │ │ 智能路由  ││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘│
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                    渠道适配层 (Channel Adapter)                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  PayStrategy (现有接口，保留)                                  │  │
│  │  ├── AbstractPayStrategy (模板方法，增强)                      │  │
│  │  ├── Wechat / Alipay / Stripe / PayPal / UnionPay / ...      │  │
│  │  └── 新渠道：实现接口 + @Component 自动注册                    │  │
│  └─────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  ChannelRouter (智能路由)                                     │  │
│  │  策略：费率优先 / 成功率优先 / 降级切换 / A/B测试 / 灰度       │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                    事件驱动层 (Event Bus)                            │
│  RocketMQ 事务消息                                                   │
│  ├── pay.created     → 通知风控/限流/日志                            │
│  ├── pay.success     → 更新订单/发通知/记账/对账预备                 │
│  ├── pay.failed      → 告警/重试/降级                               │
│  ├── refund.requested → 风控审核/退款执行                           │
│  ├── refund.success  → 更新订单/通知/记账                           │
│  └── reconcile.diff  → 告警/人工干预                                │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                    基础设施层 (Infra)                                │
│  MySQL(分库分表) │ Redis(锁+缓存+幂等) │ RocketMQ │ XXL-Job        │
│  ES(日志检索) │ ClickHouse(实时统计) │ Sentinel(限流熔断)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心设计：六层架构

### 3.1 第一层：API 接入层

```
POST   /api/v2/pay/create          → 统一下单
POST   /api/v2/pay/close           → 关闭订单
GET    /api/v2/pay/query/{orderNo} → 查询订单
POST   /api/v2/pay/refund          → 统一退款
GET    /api/v2/pay/methods         → 可用支付方式(按商户)
POST   /api/v2/pay/notify/{channel} → 统一回调入口(动态路由)
GET    /api/v2/pay/health/{channel} → 渠道健康检查
```

**统一回调入口**（解决现有 4 个硬编码回调端点问题）：

```
POST /api/v2/pay/notify/{channel}
  channel = wechat | alipay | unionpay | paypal | stripe | ...

  → NotifyController.notify(channel, request)
    → 根据 channel 找到对应 ChannelNotifyHandler
    → handler 解析 + 验签 + 转换为标准 PayNotifyResult
    → PaymentFacade.handleNotify(result)
```

### 3.2 第二层：PaymentFacade（统一编排门面）

这是**新增的核心层**，解决现有 `PaymentServiceImpl` 职责单一、缺少横切关注点的问题。

```
PaymentFacade.createPayment(dto)
  │
  ├── 1. 幂等校验：Redis SETNX pay:idempotent:{orderNo} TTL=24h
  │      └── 已存在 → 返回缓存的上次结果
  │
  ├── 2. 分布式锁：Redisson RLock pay:lock:{orderNo} waitTime=3s leaseTime=30s
  │      └── 获锁失败 → 抛异常 "订单正在处理中"
  │
  ├── 3. 状态机校验：OrderStateMachine.checkTransition(UNPAID → PAYING)
  │      └── 非法状态 → 抛异常 "订单状态不允许支付"
  │
  ├── 4. 智能路由：ChannelRouter.route(dto)
  │      └── 根据费率/成功率/降级策略选择最优渠道
  │
  ├── 5. 策略分发：PayStrategyFactory.getStrategy(payType).createPayment(dto)
  │
  ├── 6. 持久化：PaymentOrderService.save() — 保存到 payment_order 表
  │
  ├── 7. 事件发布：RocketMQ 事务消息 pay.created
  │      └── 本地事务 + MQ 发送原子性保证
  │
  └── 8. 返回结果
```

```
PaymentFacade.handleNotify(notifyResult)
  │
  ├── 1. 幂等校验：Redis SETNX pay:notify:{channel}:{outTradeNo} TTL=7d
  │      └── 已存在 → 直接返回 SUCCESS（防重复回调）
  │
  ├── 2. 分布式锁：Redisson RLock pay:notify:lock:{orderNo}
  │
  ├── 3. 状态机流转：UNPAID/PAYING → PAID
  │      └── 已 PAID → 幂等返回
  │
  ├── 4. 更新订单：PaymentOrderService.markPaid()
  │      ├── 更新 payment_status = PAID
  │      ├── 更新 callback_time, callback_content
  │      └── 更新 out_trade_no
  │
  ├── 5. 事件发布：RocketMQ pay.success
  │      └── 消费者：通知商家系统 / 记账 / 风控 / 对账预备
  │
  └── 6. 返回渠道要求的成功响应
```

### 3.3 第三层：领域服务层（DDD 聚合根）

```
spzx-model/
  └── domain/pay/
      ├── PaymentOrder          // 支付订单聚合根
      │   ├── orderNo, merchantId, amount, payType, channel
      │   ├── status (PaymentStatusEnum)
      │   ├── outTradeNo, tradeNo
      │   ├── callbackTime, callbackContent
      │   ├── expireTime
      │   └── markPaid() / markClosed() / markRefunding() / markRefunded()
      │       └── 每个方法内做状态机校验，非法流转抛异常
      │
      ├── RefundOrder           // 退款单聚合根
      │   ├── refundNo, orderNo, refundAmount, totalAmount
      │   ├── status (RefundStatusEnum)
      │   └── markRefunding() / markRefunded() / markFailed()
      │
      ├── MerchantChannel       // 商户-渠道配置聚合根
      │   ├── merchantId, channel, payTypes[]
      │   ├── feeRate, status
      │   └── isAvailable() / calculateFee()
      │
      └── PayTradeRecord        // 交易流水（不可变，审计用）
          ├── tradeNo, orderNo, channel, tradeType
          ├── amount, fee
          └── createTime (仅追加，不修改)
```

**状态机设计**：

```
支付订单状态机：
  UNPAID ──create──→ PAYING ──notify.success──→ PAID
    │                   │                        │
    │                   │                        ├── refund ──→ REFUNDING
    │                   │                        │                │
    │                   │                        │                ├── notify.success ──→ REFUNDED
    │                   │                        │                └── notify.fail ──→ REFUND_FAILED
    │                   │                        │
    │                   ├── notify.fail ──→ PAY_ERROR
    │                   ├── close ──→ CLOSED
    │                   └── timeout ──→ CLOSED (XXL-Job 定时关单)
    │
    └── cancel ──→ CLOSED

退款单状态机：
  REFUND_PENDING ──execute──→ REFUND_PROCESSING ──notify──→ REFUND_SUCCESS
                                                    └──notify.fail──→ REFUND_FAILED
                                                                    └── retry(3次) ──→ REFUND_FAILED
```

### 3.4 第四层：渠道适配层（保留+增强现有策略模式）

**保留现有 `PayStrategy` 接口不变**，增强 `AbstractPayStrategy`：

```java
// 增强后的 AbstractPayStrategy（向后兼容）
public abstract class AbstractPayStrategy implements PayStrategy {

    @Override
    public final PayCreateVO createPayment(PayCreateDTO dto) {
        validate(dto);                              // 金额校验（现有）
        preCreateHook(dto);                         // 【新增】前置钩子：风控/限流/参数补全
        PayCreateVO vo = doCreatePayment(dto);
        postCreateHook(dto, vo);                    // 【新增】后置钩子：日志/埋点/缓存
        return vo;
    }

    @Override
    public final PayNotifyResult handleNotify(String body) {
        PayNotifyResult result = doHandleNotify(body);
        // 【新增】验签已由 doHandleNotify 内部完成
        return result;
    }

    // 【新增】渠道健康检查
    public abstract boolean healthCheck();

    // 【新增】渠道费率查询
    public abstract BigDecimal getFeeRate();

    // 现有抽象方法保持不变
    protected abstract PayCreateVO doCreatePayment(PayCreateDTO dto);
    protected abstract PayNotifyResult doHandleNotify(String body);
    protected abstract RefundNotifyResult doHandleRefundNotify(String body);

    // 【新增】可重写的钩子方法（默认空实现）
    protected void preCreateHook(PayCreateDTO dto) {}
    protected void postCreateHook(PayCreateDTO dto, PayCreateVO vo) {}
}
```

**新渠道接入步骤**（证明扩展性）：

```
1. 在 PayTypeEnum 新增枚举值
2. 继承 AbstractPayStrategy（或 AbstractWechatPayStrategy 等渠道基类）
3. 实现 doCreatePayment / doHandleNotify / doHandleRefundNotify
4. 加 @Component 注解
5. 完成。PayStrategyFactory 自动注册，无需修改任何现有代码
```

**智能路由 ChannelRouter**：

```java
@Component
public class ChannelRouter {

    // 路由策略链（责任链模式）
    private final List<RouteStrategy> strategies;

    public PayTypeEnum route(PayCreateDTO dto, MerchantChannelConfig config) {
        // 1. 商户可用渠道过滤
        // 2. 费率优先：选费率最低的渠道
        // 3. 成功率优先：近1小时成功率 < 80% 的渠道降级
        // 4. 限流检查：Sentinel 限流，超限跳过
        // 5. 灰度路由：新渠道按灰度比例分流
        // 6. 降级路由：主渠道不可用 → 备用渠道
        return selectedPayType;
    }
}
```

### 3.5 第五层：事件驱动层

**RocketMQ 事务消息**保证本地事务与消息发送的原子性：

```
下单流程（事务消息）：
  1. 执行本地事务：保存 PaymentOrder(status=PAYING)
  2. 发送事务消息：pay.created
  3. RocketMQ 回查：检查 PaymentOrder 是否存在 → 决定 commit/rollback

回调流程（普通消息）：
  1. 本地事务：更新 PaymentOrder(status=PAID)
  2. 发送消息：pay.success
  3. 消费者异步处理：
     ├── MerchantNotifyConsumer → 回调商家系统（带重试3次+指数退避）
     ├── AccountingConsumer → 记账（收入/手续费/结算）
     ├── RiskControlConsumer → 风控事后分析
     └── ReconcilePrepConsumer → 写入对账预备表
```

**消息可靠性**：

```
生产者：
  - 事务消息：本地事务 + 消息发送原子性
  - 同步发送 + 重试3次

消费者：
  - 幂等消费：基于 orderNo + msgId 去重（Redis SETNX）
  - 消费失败：重试16次 → 死信队列 → 人工处理
  - 顺序消费：同一 orderNo 的消息保证顺序
```

### 3.6 第六层：基础设施层

---

## 四、数据库设计

### 4.1 分库分表策略

```
ShardingSphere-JDBC 5.5.x

分库：按 merchant_id 取模（16库）
  db_pay_0 ~ db_pay_15

分表：按 order_no hash 取模（每库16表）
  payment_order_0 ~ payment_order_15

读写分离：
  主库：写入
  从库：查询（queryPayment / 对账查询 / 报表）

广播表（不分库分表，全库同步）：
  merchant_channel_config（商户渠道配置）
  pay_channel_config（渠道全局配置）
  pay_fee_rule（费率规则）
```

### 4.2 核心表结构

```sql
-- 支付订单表（分库分表）
CREATE TABLE payment_order (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    order_no        VARCHAR(64)  NOT NULL COMMENT '商户订单号',
    out_trade_no    VARCHAR(64)  DEFAULT NULL COMMENT '渠道交易号',
    trade_no        VARCHAR(64)  DEFAULT NULL COMMENT '渠道流水号',
    merchant_id     BIGINT       NOT NULL COMMENT '商户ID',
    merchant_name   VARCHAR(128) DEFAULT NULL,
    pay_type        TINYINT      NOT NULL COMMENT '支付方式 PayTypeEnum',
    channel         VARCHAR(32)  NOT NULL COMMENT '支付渠道',
    amount          DECIMAL(18,4) NOT NULL COMMENT '支付金额',
    fee             DECIMAL(18,4) DEFAULT 0 COMMENT '手续费',
    subject         VARCHAR(256) DEFAULT NULL,
    body            TEXT         DEFAULT NULL COMMENT '商品描述',
    attach          VARCHAR(512) DEFAULT NULL COMMENT '附加数据',
    status          TINYINT      NOT NULL DEFAULT 0 COMMENT 'PaymentStatusEnum',
    client_ip       VARCHAR(64)  DEFAULT NULL,
    notify_url      VARCHAR(512) DEFAULT NULL COMMENT '商户回调地址',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    expire_time     DATETIME(3)  DEFAULT NULL COMMENT '订单过期时间',
    callback_time   DATETIME(3)  DEFAULT NULL,
    callback_content TEXT        DEFAULT NULL,
    callback_count  INT          DEFAULT 0 COMMENT '回调次数',
    next_notify_time DATETIME(3) DEFAULT NULL COMMENT '下次通知商户时间',
    platform_type   INT          DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),          -- 【关键】唯一索引，DB层幂等
    KEY idx_out_trade_no (out_trade_no),
    KEY idx_merchant_status (merchant_id, status),
    KEY idx_channel_trade (channel, out_trade_no),
    KEY idx_create_time (create_time)
) ENGINE=InnoDB COMMENT='支付订单';

-- 退款单表（分库分表）
CREATE TABLE refund_order (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    refund_no       VARCHAR(64)  NOT NULL COMMENT '退款单号',
    order_no        VARCHAR(64)  NOT NULL COMMENT '原支付订单号',
    out_refund_no   VARCHAR(64)  DEFAULT NULL COMMENT '渠道退款号',
    merchant_id     BIGINT       NOT NULL,
    channel         VARCHAR(32)  NOT NULL,
    refund_amount   DECIMAL(18,4) NOT NULL,
    total_amount    DECIMAL(18,4) NOT NULL COMMENT '原订单总额',
    reason          VARCHAR(256) DEFAULT NULL,
    status          TINYINT      NOT NULL DEFAULT 0 COMMENT 'RefundStatusEnum',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    callback_time   DATETIME(3)  DEFAULT NULL,
    callback_content TEXT        DEFAULT NULL,
    retry_count     INT          DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uk_refund_no (refund_no),
    KEY idx_order_no (order_no),
    KEY idx_merchant_status (merchant_id, status)
) ENGINE=InnoDB COMMENT='退款单';

-- 交易流水表（仅追加，审计用，分库分表）
CREATE TABLE pay_trade_record (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    trade_no        VARCHAR(64)  NOT NULL COMMENT '平台流水号(snowflake)',
    order_no        VARCHAR(64)  NOT NULL,
    refund_no       VARCHAR(64)  DEFAULT NULL,
    merchant_id     BIGINT       NOT NULL,
    channel         VARCHAR(32)  NOT NULL,
    trade_type      VARCHAR(16)  NOT NULL COMMENT 'PAY/REFUND/QUERY/CLOSE',
    amount          DECIMAL(18,4) NOT NULL,
    fee             DECIMAL(18,4) DEFAULT 0,
    result          TINYINT      NOT NULL COMMENT '0-fail 1-success',
    channel_resp    TEXT         DEFAULT NULL,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_trade_no (trade_no),
    KEY idx_order_no (order_no),
    KEY idx_channel_time (channel, create_time)
) ENGINE=InnoDB COMMENT='交易流水(不可变)';

-- 商户回调通知表（通知商家系统的记录）
CREATE TABLE merchant_notify_record (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    order_no        VARCHAR(64)  NOT NULL,
    notify_type     VARCHAR(16)  NOT NULL COMMENT 'PAY/REFUND',
    notify_url      VARCHAR(512) NOT NULL,
    notify_content  TEXT         NOT NULL,
    notify_count    INT          NOT NULL DEFAULT 0,
    notify_status   TINYINT      NOT NULL DEFAULT 0 COMMENT '0-pending 1-success 2-fail',
    next_notify_time DATETIME(3) DEFAULT NULL,
    response_content VARCHAR(512) DEFAULT NULL,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_order_no (order_no),
    KEY idx_status_next (notify_status, next_notify_time)
) ENGINE=InnoDB COMMENT='商户回调通知';

-- 对账明细表
CREATE TABLE reconcile_detail (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    batch_id        VARCHAR(64)  NOT NULL COMMENT '对账批次号',
    reconcile_date  DATE         NOT NULL,
    channel         VARCHAR(32)  NOT NULL,
    order_no        VARCHAR(64)  NOT NULL,
    platform_amount DECIMAL(18,4) NOT NULL,
    channel_amount  DECIMAL(18,4) DEFAULT NULL,
    platform_status TINYINT      NOT NULL,
    channel_status  VARCHAR(32)  DEFAULT NULL,
    diff_type       VARCHAR(16)  DEFAULT NULL COMMENT 'NONE/AMOUNT/STATUS/MISSING_LOCAL/MISSING_CHANNEL',
    handled         TINYINT      NOT NULL DEFAULT 0,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_batch (batch_id),
    KEY idx_date_channel (reconcile_date, channel),
    KEY idx_diff (diff_type, handled)
) ENGINE=InnoDB COMMENT='对账明细';

-- 商户渠道配置（广播表）
CREATE TABLE merchant_channel_config (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    merchant_id     BIGINT       NOT NULL,
    channel         VARCHAR(32)  NOT NULL,
    pay_types       VARCHAR(256) NOT NULL COMMENT '支持的支付方式,逗号分隔',
    fee_rate        DECIMAL(8,6) NOT NULL DEFAULT 0.006 COMMENT '费率',
    status          TINYINT      NOT NULL DEFAULT 1 COMMENT '0-disabled 1-enabled',
    priority        INT          NOT NULL DEFAULT 0 COMMENT '路由优先级',
    daily_limit     DECIMAL(18,4) DEFAULT NULL COMMENT '日交易限额',
    config_extra    JSON         DEFAULT NULL COMMENT '渠道特有配置',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_merchant_channel (merchant_id, channel)
) ENGINE=InnoDB COMMENT='商户渠道配置';

-- 渠道全局配置（广播表）
CREATE TABLE pay_channel_config (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    channel         VARCHAR(32)  NOT NULL,
    status          TINYINT      NOT NULL DEFAULT 1 COMMENT '渠道全局开关',
    weight          INT          NOT NULL DEFAULT 100 COMMENT '路由权重',
    fallback_channel VARCHAR(32) DEFAULT NULL COMMENT '降级备用渠道',
    config_extra    JSON         DEFAULT NULL,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_channel (channel)
) ENGINE=InnoDB COMMENT='渠道全局配置';
```

### 4.3 现有表迁移

```
payment_info → payment_order (重命名 + 字段补齐 + 加唯一索引)
  - pay_type: Byte → TINYINT (兼容25+种枚举)
  - payment_status: String → TINYINT (枚举化)
  - 新增: merchant_id, channel, fee, expire_time, notify_url, callback_count
  - uk_order_no: NON_UNIQUE → UNIQUE (DB层幂等保障)
```

---

## 五、高并发设计

### 5.1 全链路异步化

```
下单请求：
  Controller → Facade(同步：幂等+锁+状态机+持久化) → Strategy(同步：调渠道SDK)
  → MQ(异步：发事件) → 消费者(异步：通知商家/记账/风控)

回调请求：
  Controller → Facade(同步：幂等+锁+状态机+更新订单)
  → MQ(异步：发事件) → 消费者(异步：通知商家/记账/风控)

  关键：回调处理只做"更新订单状态"这一件事（<10ms），其余全部异步
  → 回调响应时间 < 50ms，不会因为下游慢导致渠道重试
```

### 5.2 分库分表 + 读写分离

```
写入：16库 × 16表 = 256个物理表，按 merchant_id 分库、order_no 分表
查询：
  - 指定 orderNo：精准路由到单表（90%查询场景）
  - 按 merchantId + 时间范围：路由到单库多表，并行查询
  - 聚合统计：ClickHouse 预计算，不走 MySQL

QPS 估算：
  单表 2000 QPS × 256 表 = 理论 51万 QPS（写入）
  实际受限于 16 个 MySQL 实例，按每实例 3万 QPS ≈ 48万 QPS
```

### 5.3 Redis 多级缓存

```
L1 本地缓存 (Caffeine, 5s TTL)：
  - merchant_channel_config（商户渠道配置，变更少）
  - pay_channel_config（渠道全局配置）
  - PayTypeEnum 枚举映射

L2 Redis (30s TTL)：
  - pay:methods:{merchantId} → 可用支付方式列表
  - pay:fee:{merchantId}:{channel} → 费率
  - pay:health:{channel} → 渠道健康状态（Sentinel 心跳）

L3 MySQL：
  - 兜底数据源
```

### 5.4 Sentinel 限流熔断

```yaml
# 支付下单限流
- resource: payCreate
  flowRule:
    count: 2000        # 每秒2000次
    grade: QPS
    strategy: direct
    controlBehavior: warm_up   # 预热
    warmUpPeriodSec: 30

# 渠道调用熔断
- resource: channelCall:wechat
  degradeRule:
    count: 500ms       # RT > 500ms
    timeWindow: 10s    # 10秒内超过50%请求慢 → 熔断10秒
    minRequestAmount: 5

- resource: channelCall:alipay
  degradeRule:
    count: 500ms
    timeWindow: 10s
    minRequestAmount: 5

# 回调处理限流（防渠道洪峰重试）
- resource: payNotify
  flowRule:
    count: 5000
    grade: QPS
```

### 5.5 虚拟线程（JDK 21）

```java
// 支付回调使用虚拟线程，避免回调洪峰耗尽线程池
@RestController
public class NotifyController {
    // Spring Boot 3 + JDK 21 自动使用虚拟线程处理请求
    // 配置：spring.threads.virtual.enabled=true
}

// MQ 消费者使用虚拟线程
@RocketMQMessageListener(consumerThread = "virtual")
```

---

## 六、高可用设计

### 6.1 渠道降级与故障转移

```
ChannelRouter 降级链：
  微信 → 支付宝 → 银联（备用）

触发条件：
  1. 渠道 healthCheck() 失败 → 标记不可用 → 路由跳过
  2. Sentinel 熔断触发 → 10秒内跳过
  3. 连续失败 > 阈值 → 熔断 30s → 半开探测 → 恢复

恢复：
  半开状态发探测请求 → 成功 → 关闭熔断
  XXL-Job 每 30s 调用 healthCheck() → 恢复标记
```

### 6.2 幂等性三重保障

```
第一重：Redis SETNX（快速拦截）
  pay:idempotent:{orderNo}  TTL=24h  → 下单幂等
  pay:notify:{channel}:{outTradeNo}  TTL=7d  → 回调幂等
  pay:refund:{refundNo}  TTL=24h  → 退款幂等

第二重：DB 唯一索引（强一致兜底）
  payment_order.uk_order_no
  refund_order.uk_refund_no

第三重：状态机校验（语义正确性）
  已 PAID 的订单收到回调 → 幂等返回 SUCCESS
  已 REFUNDED 的退款单收到重复退款请求 → 幂等返回
```

### 6.3 回调通知商家重试机制

```
RocketMQ 消费者 → MerchantNotifyConsumer

通知策略（与微信/支付宝一致）：
  第1次：立即
  第2次：15s 后
  第3次：1min 后
  第4次：5min 后
  第5次：10min 后
  第6次：30min 后
  第7次：1h 后
  第8次：2h 后
  ...最多 15 次，超过 24h → 标记通知失败 → 告警

实现：
  - merchant_notify_record 表记录通知状态和下次通知时间
  - XXL-Job 每 10s 扫描 next_notify_time <= now 的记录，重试发送
  - 商家返回 200 + "success" → 标记成功
  - 其他 → 记录 response，更新下次通知时间
```

### 6.4 定时对账

```
XXL-Job 对账任务：

每日对账（T+1 凌晨3点）：
  1. 下载渠道对账单（微信/支付宝/Stripe 各自 API）
  2. 解析对账单 → 写入 reconcile_detail
  3. 拉取平台当日 payment_order 数据
  4. 逐笔比对：金额 / 状态 / 存在性
  5. 差异分类：
     - AMOUNT_DIFF：金额不一致
     - STATUS_DIFF：状态不一致
     - MISSING_LOCAL：渠道有、平台无（漏单）
     - MISSING_CHANNEL：平台有、渠道无（单边账）
  6. 差异写入 reconcile_detail，diff_type != NONE
  7. 发送 reconcile.diff 事件 → 告警 + 人工处理

实时对账（每5分钟）：
  对比最近5分钟的 payment_order 与渠道查询结果
  发现差异 → 实时告警（不等到T+1）
```

### 6.5 订单超时关单

```
XXL-Job 每 1 分钟执行：
  SELECT order_no, channel FROM payment_order
  WHERE status = 0 (UNPAID)
    AND expire_time <= NOW()
  LIMIT 1000

  → 逐笔调用 PayStrategy.closePayment()
  → 更新 status = CLOSED
  → 发送 pay.closed 事件
```

### 6.6 退款补偿

```
退款失败自动重试（最多3次）：
  XXL-Job 每 5 分钟执行：
    SELECT * FROM refund_order
    WHERE status = REFUND_FAILED AND retry_count < 3

    → 重新调用 PayStrategy.refund()
    → 成功 → status = REFUND_PROCESSING
    → 失败 → retry_count++ → 3次后标记需人工处理 → 告警
```

---

## 七、安全设计

### 7.1 签名验证

```
商户请求签名（API 接入）：
  1. 商户分配 apiKey + apiSecret
  2. 请求参数按字典序排序 → 拼接 → HMAC-SHA256(apiSecret) → sign
  3. 网关验签：验签失败 → 403

渠道回调验签（已有，保留）：
  - 微信：WxJava SDK parseOrderNotifyV3Result 内部验签
  - 支付宝：AlipaySignature.rsaCheckV1
  - Stripe：Webhook 签名校验（X-Signature header）
  - 新渠道：在 doHandleNotify 内部完成验签
```

### 7.2 敏感数据保护

```
渠道密钥存储：
  - 开发环境：application-dev.yml 明文（现有，环境变量覆盖）
  - 生产环境：Nacos 配置中心加密配置项
  - 密钥轮换：支持热更新，不重启应用

数据库：
  - callback_content / channel_resp：敏感字段可选 AES 加密存储
  - merchant apiSecret：BCrypt 存储（不可逆）
```

### 7.3 回调白名单

```
现有问题：/api/pay/notify/** 未加入 Constant.whiteList

修复：
  Constant.whiteList 增加：
    /api/pay/notify/**
    /api/v2/pay/notify/**

  或使用 @AnonymousAccess 注解标注回调端点
```

---

## 八、模块代码结构

```
spzx-manager/
  └── src/main/java/com/joker/spzx/manager/
      ├── controller/
      │   ├── PaymentController.java          # 现有，保留（v1 兼容）
      │   ├── PayV2Controller.java            # 【新】v2 API
      │   ├── NotifyController.java           # 【新】统一回调入口
      │   └── ReconcileController.java        # 【新】对账管理
      │
      ├── facade/
      │   └── PaymentFacade.java             # 【新】统一编排门面
      │
      ├── domain/                             # 【新】领域服务
      │   ├── PaymentOrderDomainService.java
      │   ├── RefundOrderDomainService.java
      │   ├── MerchantChannelDomainService.java
      │   └── state/
      │       ├── PaymentStateMachine.java
      │       └── RefundStateMachine.java
      │
      ├── pay/                                # 现有，增强
      │   ├── strategy/
      │   │   ├── PayStrategy.java            # 现有，不变
      │   │   ├── AbstractPayStrategy.java    # 增强：钩子 + healthCheck
      │   │   ├── PayStrategyFactory.java     # 现有，不变
      │   │   ├── ChannelRouter.java          # 【新】智能路由
      │   │   └── impl/                       # 现有策略 + 新渠道策略
      │   ├── config/                         # 现有，增强
      │   ├── handler/                        # 【新】回调处理器
      │   │   ├── ChannelNotifyHandler.java   # 接口
      │   │   ├── WechatNotifyHandler.java
      │   │   ├── AlipayNotifyHandler.java
      │   │   └── NotifyHandlerFactory.java
      │   └── event/                          # 【新】事件定义
      │       ├── PayCreatedEvent.java
      │       ├── PaySuccessEvent.java
      │       ├── PayFailedEvent.java
      │       ├── RefundRequestedEvent.java
      │       └── RefundSuccessEvent.java
      │
      ├── mq/                                 # 【新】消息消费者
      │   ├── MerchantNotifyConsumer.java
      │   ├── AccountingConsumer.java
      │   ├── RiskControlConsumer.java
      │   └── ReconcilePrepConsumer.java
      │
      ├── job/                                # 【新】定时任务
      │   ├── OrderTimeoutJob.java            # 超时关单
      │   ├── RefundRetryJob.java             # 退款重试
      │   ├── DailyReconcileJob.java          # 每日对账
      │   ├── RealtimeReconcileJob.java       # 实时对账
      │   ├── MerchantNotifyRetryJob.java    # 商户通知重试
      │   └── ChannelHealthCheckJob.java      # 渠道健康检查
      │
      ├── service/
      │   ├── PaymentService.java             # 现有，保留
      │   ├── impl/PaymentServiceImpl.java    # 现有，保留（v1 兼容）
      │   ├── PaymentOrderService.java        # 【新】订单CRUD
      │   ├── RefundOrderService.java         # 【新】退款CRUD
      │   ├── MerchantNotifyService.java      # 【新】商户通知
      │   ├── ReconcileService.java           # 【新】对账
      │   └── IdempotentService.java          # 【新】幂等服务
      │
      └── config/
          ├── ShardingConfig.java             # 【新】分库分表
          ├── RocketMQConfig.java             # 【新】MQ配置
          ├── RedissonConfig.java             # 【新】分布式锁
          └── VirtualThreadConfig.java        # 【新】虚拟线程

spzx-model/
  └── src/main/java/com/joker/spzx/model/
      ├── domain/pay/                         # 【新】领域模型
      │   ├── PaymentOrder.java
      │   ├── RefundOrder.java
      │   ├── MerchantChannel.java
      │   └── PayTradeRecord.java
      ├── enums/pay/
      │   ├── PayTypeEnum.java               # 现有，扩展
      │   ├── PaymentStatusEnum.java          # 现有，扩展
      │   ├── RefundStatusEnum.java           # 【新】
      │   ├── ChannelEnum.java                # 【新】
      │   └── ReconcileDiffTypeEnum.java      # 【新】
      ├── dto/pay/
      │   ├── PayCreateDTO.java              # 现有，增强
      │   ├── RefundCreateDTO.java            # 现有，增强
      │   ├── PayQueryDTO.java                # 【新】
      │   ├── ReconcileDTO.java               # 【新】
      │   └── MerchantNotifyDTO.java         # 【新】
      └── vo/pay/
          ├── PayCreateVO.java               # 现有
          ├── PayNotifyResult.java            # 现有，增强
          ├── PayQueryVO.java                 # 现有
          ├── RefundNotifyResult.java         # 现有
          └── ReconcileResultVO.java          # 【新】
```

---

## 九、与现有代码的兼容策略

### 9.1 保留不动

```
✅ PayStrategy 接口 — 不变
✅ PayStrategyFactory — 不变（自动注册新策略）
✅ PayTypeEnum — 只增不删
✅ 所有现有策略类 — 不变（AbstractPayStrategy 增强向后兼容）
✅ PaymentController (v1) — 保留，标记 @Deprecated
✅ PaymentService / PaymentServiceImpl — 保留，v1 流量继续走
✅ 所有配置类 — 不变，新增配置项用默认值
```

### 9.2 增量新增

```
➕ PayV2Controller — v2 API，走 PaymentFacade
➕ PaymentFacade — 新编排层
➕ 领域模型 + 状态机
➕ MQ 消费者
➕ 定时任务
➕ 分库分表配置
➕ 对账模块
➕ 智能路由
```

### 9.3 数据迁移

```
1. 新建 payment_order / refund_order / pay_trade_record 等表
2. 数据迁移：payment_info → payment_order（字段映射 + 类型转换）
3. uk_order_no 改为 UNIQUE INDEX
4. 灰度切换：v2 API 灰度 10% → 50% → 100%
5. v1 下线
```

---

## 十、技术选型补充

| 组件 | 选型 | 版本 | 用途 |
|------|------|------|------|
| 分布式锁 | Redisson | 3.37.0 | 下单/回调互斥 |
| 消息队列 | RocketMQ | 5.3.x | 事务消息 + 事件驱动 |
| 分库分表 | ShardingSphere-JDBC | 5.5.x | 分库分表 + 读写分离 |
| 限流熔断 | Sentinel | 1.8.8 | 渠道级限流熔断 |
| 定时任务 | XXL-Job | 2.4.2 | 对账/关单/重试 |
| ID 生成 | Snowflake(内置) | — | tradeNo 全局唯一 |
| 本地缓存 | Caffeine | 3.1.8 | 渠道配置热缓存 |
| HTTP 客户端 | OkHttp / WebClient | — | 渠道 API 调用 |

---

## 十一、实施路线图

### 第一阶段：补齐基础（1-2 周）

```
目标：修复现有严重缺陷，不改变架构
  [ ] 回调白名单加入 /api/pay/notify/**
  [ ] 回调后持久化：更新 payment_info 状态
  [ ] payment_info.uk_order_no 改为唯一索引
  [ ] PaymentInfo.pay_type: Byte → Integer
  [ ] PaymentInfo.payment_status: String → Integer
  [ ] 补齐 PayPal 下单 bug（requestBody 未设置）
  [ ] 补齐 Stripe 退款参数语义
  [ ] 补齐支付宝回调 scan/mini 策略选择
```

### 第二阶段：幂等 + 状态机（2-3 周）

```
目标：资金安全基础保障
  [ ] IdempotentService（Redis SETNX 幂等）
  [ ] PaymentStateMachine / RefundStateMachine
  [ ] Redisson 分布式锁
  [ ] 回调幂等：基于 outTradeNo 去重
  [ ] 下单幂等：基于 orderNo 去重
  [ ] 单元测试：状态机流转 + 幂等并发
```

### 第三阶段：领域模型 + v2 API（3-4 周）

```
目标：DDD 重构，双版本并行
  [ ] PaymentOrder / RefundOrder 聚合根
  [ ] PaymentFacade 统一编排
  [ ] PayV2Controller + NotifyController
  [ ] 数据迁移：payment_info → payment_order
  [ ] 灰度切流 v2
```

### 第四阶段：事件驱动（4-5 周）

```
目标：异步解耦
  [ ] RocketMQ 接入 + 事务消息
  [ ] 事件定义（pay.created/success/failed...）
  [ ] MerchantNotifyConsumer + 重试机制
  [ ] AccountingConsumer
  [ ] MerchantNotifyRetryJob
  [ ] 顺序消费 + 幂等消费
```

### 第五阶段：高并发（5-6 周）

```
目标：性能提升
  [ ] ShardingSphere 分库分表（16库×16表）
  [ ] 读写分离
  [ ] Caffeine + Redis 多级缓存
  [ ] Sentinel 限流熔断规则
  [ ] JDK 21 虚拟线程启用
  [ ] 压测：下单 2000 QPS / 回调 5000 QPS
```

### 第六阶段：高可用（6-8 周）

```
目标：故障自愈
  [ ] ChannelRouter 智能路由 + 降级
  [ ] ChannelHealthCheckJob 渠道健康检查
  [ ] OrderTimeoutJob 超时关单
  [ ] RefundRetryJob 退款重试
  [ ] DailyReconcileJob + RealtimeReconcileJob 对账
  [ ] 监控告警：Prometheus 指标 + Grafana 大屏 + 钉钉告警
  [ ] 补齐剩余 5 渠道 SDK 集成（银联/抖音/京东/拉卡拉/聚合）
```

---

## 十二、监控指标

```
业务指标（Grafana 大屏）：
  - 支付成功率（按渠道/商户/支付方式维度）
  - 支付 RT P99/P95（按渠道维度）
  - 退款成功率
  - 日交易额 / 日手续费收入
  - 对账差异笔数

系统指标（Prometheus）：
  - 下单 QPS / 回调 QPS
  - 渠道调用 RT + 成功率
  - MQ 消息积压量
  - 分布式锁等待时间
  - 分库分表各分片流量分布

告警规则：
  - 支付成功率 < 95% → P1 告警
  - 渠道 RT P99 > 2s → P2 告警
  - 对账差异 > 0 → P1 告警
  - MQ 积压 > 10000 → P2 告警
  - 渠道熔断触发 → P1 告警
  - 退款失败需人工处理 → P3 告警
```

---

## 十三、关键约束

1. **PayStrategy 接口永不改变** — 新增能力通过 default 方法或抽象类钩子扩展，保证所有现有策略类零改动
2. **PaymentFacade 是唯一的业务编排入口** — v2 API 必须经过 Facade，不允许 Controller 直接调 Strategy
3. **回调处理只做一件事** — 更新订单状态，其余全部异步 MQ，保证回调响应 < 50ms
4. **三重幂等缺一不可** — Redis 快速拦截 + DB 唯一索引兜底 + 状态机语义校验
5. **资金操作必须有事前对账预备** — 每笔成功支付写入 reconcile 预备表，T+1 对账
6. **渠道降级必须自动化** — 不依赖人工切换，ChannelRouter + Sentinel + HealthCheck 三层保障
7. **分库分表键不可更改** — merchant_id 分库 + order_no 分表，选型后不可变
8. **v1/v2 双版本并行** — 灰度切流，v1 至少保留到 v2 稳定运行 30 天后才下线

---

## 十四、风控系统设计

支付中台必须具备三层风控能力，否则无法应对盗刷、套现、洗钱等风险。

### 14.1 三层风控架构

```
┌─────────────────────────────────────────────────────────┐
│                   事前风控 (Pre-Risk)                     │
│  时机：下单前，同步拦截（< 20ms）                         │
│  目标：快速拒绝明显异常请求                               │
├─────────────────────────────────────────────────────────┤
│  规则引擎（Redis + Lua 原子执行）：                       │
│  ├── 单 IP 限频：同 IP 1分钟内下单 > 20 次 → 拦截         │
│  ├── 单用户限频：同 userId 1分钟内下单 > 10 次 → 拦截     │
│  ├── 单设备限频：同 deviceId 1小时内下单 > 50 次 → 拦截   │
│  ├── 金额异常：单笔 > 商户日均 × 10 → 人工审核           │
│  ├── 黑名单：IP / userId / deviceId / 卡号 → 直接拦截    │
│  ├── 地域风控：高风险地区 IP → 加验                       │
│  └── 商户限额：商户日累计交易额 > daily_limit → 拦截      │
├─────────────────────────────────────────────────────────┤
│  实现：RiskRuleEngine.execute(RiskContext) → RiskResult  │
│  RiskResult: PASS / REJECT / REVIEW                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   事中风控 (In-Risk)                      │
│  时机：渠道下单时，异步分析（不阻塞主流程）                │
│  目标：实时识别异常交易模式                                │
├─────────────────────────────────────────────────────────┤
│  Flink CEP（复杂事件处理）：                              │
│  ├── 同用户 5 分钟内多渠道支付 → 疑似盗刷 → 冻结          │
│  ├── 同设备 1 小时内不同用户支付 → 疑似刷单 → 告警        │
│  ├── 退款率突增：商户 1 小时退款率 > 30% → 降级           │
│  ├── 金额聚集：同金额高频出现 → 疑似测试 → 告警           │
│  └── 渠道成功率突降：< 80% → 自动降级备用渠道             │
├─────────────────────────────────────────────────────────┤
│  实现：pay.created 事件 → Flink CEP → RiskAlert          │
│  RiskAlert 级别：INFO / WARN / CRITICAL                  │
│  CRITICAL → 调用 FreezeService 冻结订单/商户              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   事后风控 (Post-Risk)                    │
│  时机：支付成功后，异步分析 + T+1 离线分析                 │
│  目标：发现遗漏风险，沉淀风控模型                          │
├─────────────────────────────────────────────────────────┤
│  实时（pay.success 事件 → RiskControlConsumer）：         │
│  ├── 写入风控特征库（用户/商户/渠道维度）                  │
│  ├── 更新风控评分（Redis 滑动窗口）                       │
│  └── 触发告警规则                                         │
│                                                          │
│  离线（Spark T+1）：                                      │
│  ├── 商户风险画像：交易量/退款率/投诉率/异常率             │
│  ├── 用户风险画像：消费习惯/设备指纹/地域分布              │
│  ├── 关联网络分析：同设备/同IP/同卡号的用户关联            │
│  └── 模型训练：ML 风控评分模型迭代                        │
└─────────────────────────────────────────────────────────┘
```

### 14.2 风控规则引擎核心设计

```java
// 风控上下文（贯穿三层风控）
public class RiskContext {
    private String orderNo;
    private Long merchantId;
    private Long userId;
    private String clientIp;
    private String deviceId;
    private BigDecimal amount;
    private String channel;
    private Integer payType;
    private Map<String, Object> extra;  // 渠道特有数据
}

// 风控结果
public class RiskResult {
    private RiskAction action;    // PASS / REJECT / REVIEW
    private String ruleCode;      // 命中的规则编码
    private String reason;        // 拦截原因
    private int riskScore;        // 风险评分 0-100
}

// 规则接口（策略模式，每条规则一个实现）
public interface RiskRule {
    String getCode();
    RiskResult evaluate(RiskContext ctx);
    int getPriority();  // 越小越先执行
}

// 规则引擎
@Component
public class RiskRuleEngine {
    private final List<RiskRule> rules;  // Spring 自动注入，按 priority 排序

    public RiskResult execute(RiskContext ctx) {
        for (RiskRule rule : rules) {
            RiskResult result = rule.evaluate(ctx);
            if (result.getAction() == RiskAction.REJECT) {
                return result;  // 短路返回，立即拦截
            }
        }
        return RiskResult.pass();
    }
}
```

### 14.3 风控数据表

```sql
-- 风控规则表
CREATE TABLE risk_rule (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    rule_code       VARCHAR(64)  NOT NULL,
    rule_name       VARCHAR(128) NOT NULL,
    rule_type       VARCHAR(16)  NOT NULL COMMENT 'PRE/IN/POST',
    rule_config     JSON         NOT NULL COMMENT '规则参数',
    action          VARCHAR(16)  NOT NULL COMMENT 'REJECT/REVIEW',
    priority        INT          NOT NULL DEFAULT 100,
    status          TINYINT      NOT NULL DEFAULT 1,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_rule_code (rule_code)
) ENGINE=InnoDB COMMENT='风控规则';

-- 风控命中记录
CREATE TABLE risk_hit_record (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    order_no        VARCHAR(64)  NOT NULL,
    rule_code       VARCHAR(64)  NOT NULL,
    action          VARCHAR(16)  NOT NULL,
    risk_score      INT          NOT NULL,
    context_snapshot JSON       NOT NULL COMMENT '风控上下文快照',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_order_no (order_no),
    KEY idx_rule_time (rule_code, create_time)
) ENGINE=InnoDB COMMENT='风控命中记录';

-- 黑名单表
CREATE TABLE risk_blacklist (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    black_type      VARCHAR(16)  NOT NULL COMMENT 'IP/USER/DEVICE/MERCHANT/CARD',
    black_value     VARCHAR(256) NOT NULL,
    reason          VARCHAR(256) DEFAULT NULL,
    expire_time     DATETIME(3)  DEFAULT NULL COMMENT 'NULL=永久',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_type_value (black_type, black_value)
) ENGINE=InnoDB COMMENT='风控黑名单';
```

---

## 十五、商户接入与多租户体系

### 15.1 商户模型

```
平台运营方
  └── 商户 (Merchant)
      ├── 商户基本信息：名称/联系方式/营业执照
      ├── 商户密钥：apiKey + apiSecret（BCrypt 存储）
      ├── 渠道配置：merchant_channel_config（每渠道独立费率/限额）
      ├── 结算账户：银行账户/支付宝账号
      └── 风控配置：限额/黑名单/审核规则
```

### 15.2 商户接入流程

```
1. 商户注册 → 提交资质 → 平台审核
2. 审核通过 → 分配 apiKey + apiSecret
3. 配置支付渠道 → 绑定渠道商户号 → 设置费率
4. 配置回调地址 → 验证回调可达性
5. 沙箱测试 → 联调通过 → 切换生产环境
6. 上线监控 → 首日人工巡检
```

### 15.3 多租户隔离

```
数据隔离：
  - 分库分表按 merchant_id 路由，物理隔离
  - 广播表(merchant_channel_config)按 merchant_id 过滤

资源隔离：
  - Sentinel 限流按 merchantId 维度独立计数
  - Redis key 以 merchantId 为前缀：pay:{merchantId}:*

配置隔离：
  - 每商户独立费率/限额/回调地址
  - 渠道配置支持商户级覆盖（merchant_channel_config.config_extra）
```

### 15.4 商户数据表

```sql
-- 商户表
CREATE TABLE pay_merchant (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    merchant_no     VARCHAR(32)  NOT NULL COMMENT '商户编号',
    merchant_name   VARCHAR(128) NOT NULL,
    api_key         VARCHAR(64)  NOT NULL,
    api_secret      VARCHAR(128) NOT NULL COMMENT 'BCrypt加密',
    contact_name    VARCHAR(64)  DEFAULT NULL,
    contact_phone   VARCHAR(32)  DEFAULT NULL,
    business_license VARCHAR(128) DEFAULT NULL,
    status          TINYINT      NOT NULL DEFAULT 0 COMMENT '0-待审核 1-正常 2-冻结 3-注销',
    env             VARCHAR(8)   NOT NULL DEFAULT 'sandbox' COMMENT 'sandbox/production',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_merchant_no (merchant_no),
    UNIQUE KEY uk_api_key (api_key)
) ENGINE=InnoDB COMMENT='支付商户';

-- 商户结算账户
CREATE TABLE merchant_settle_account (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    merchant_id     BIGINT       NOT NULL,
    account_type    VARCHAR(16)  NOT NULL COMMENT 'BANK/ALIPAY/WECHAT',
    account_name    VARCHAR(128) NOT NULL,
    account_no      VARCHAR(64)  NOT NULL,
    bank_code       VARCHAR(32)  DEFAULT NULL,
    is_default      TINYINT      NOT NULL DEFAULT 0,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_merchant (merchant_id)
) ENGINE=InnoDB COMMENT='商户结算账户';
```

---

## 十六、资金结算与记账体系

### 16.1 资金流向

```
用户支付 → 渠道收款 → 平台在途资金 → T+1 结算 → 商户可用余额 → 商户提现

  支付成功：
    用户账户 ──amount──→ 渠道账户
    平台记账：在途资金 += amount，手续费收入 += fee

  T+1 结算：
    平台在途 ──(amount-fee)──→ 商户可用余额
    平台记账：在途资金 -= amount，商户余额 += (amount-fee)

  商户提现：
    商户可用余额 ──withdraw──→ 商户银行账户
    平台记账：商户余额 -= withdraw，提现中 += withdraw

  提现到账：
    提现中 -= withdraw
```

### 16.2 复式记账（双账本）

```
每笔交易产生两条记账记录（有借必有贷，借贷必相等）：

  支付成功：
    借：在途资金(merchantId)  amount
    贷：应付商户(merchantId)  amount

  手续费：
    借：手续费支出(merchantId)  fee
    贷：在途资金(merchantId)    fee

  结算：
    借：应付商户(merchantId)  amount
    贷：商户余额(merchantId)  amount-fee
    贷：手续费收入(platform)  fee

  退款：
    借：应付商户(merchantId)  refundAmount
    贷：在途资金(merchantId)  refundAmount
```

### 16.3 结算数据表

```sql
-- 账户表（商户虚拟账户）
CREATE TABLE pay_account (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    merchant_id     BIGINT       NOT NULL,
    account_type    VARCHAR(16)  NOT NULL COMMENT 'SETTLE/IN_TRANSIT',
    balance         DECIMAL(18,4) NOT NULL DEFAULT 0 COMMENT '可用余额',
    frozen_balance  DECIMAL(18,4) NOT NULL DEFAULT 0 COMMENT '冻结余额',
    in_transit      DECIMAL(18,4) NOT NULL DEFAULT 0 COMMENT '在途金额',
    version         INT          NOT NULL DEFAULT 0 COMMENT '乐观锁版本号',
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_merchant_type (merchant_id, account_type)
) ENGINE=InnoDB COMMENT='支付账户';

-- 记账流水表（复式记账，仅追加）
CREATE TABLE account_entry (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    entry_no        VARCHAR(64)  NOT NULL COMMENT '记账凭证号',
    account_id      BIGINT       NOT NULL,
    direction       VARCHAR(4)   NOT NULL COMMENT 'DEBIT/CREDIT',
    amount          DECIMAL(18,4) NOT NULL,
    balance_after   DECIMAL(18,4) NOT NULL COMMENT '记账后余额(快照)',
    biz_type        VARCHAR(16)  NOT NULL COMMENT 'PAY/REFUND/FEE/SETTLE/WITHDRAW',
    biz_order_no    VARCHAR(64)  NOT NULL,
    merchant_id     BIGINT       NOT NULL,
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_entry_no (entry_no),
    KEY idx_account (account_id, create_time),
    KEY idx_biz (biz_type, biz_order_no)
) ENGINE=InnoDB COMMENT='记账流水';

-- 结算单
CREATE TABLE settle_batch (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    batch_no        VARCHAR(64)  NOT NULL,
    merchant_id     BIGINT       NOT NULL,
    settle_date     DATE         NOT NULL,
    total_amount    DECIMAL(18,4) NOT NULL COMMENT '结算总额',
    total_fee       DECIMAL(18,4) NOT NULL COMMENT '手续费总额',
    net_amount      DECIMAL(18,4) NOT NULL COMMENT '净结算额',
    order_count     INT          NOT NULL,
    status          TINYINT      NOT NULL DEFAULT 0 COMMENT '0-待结算 1-结算中 2-已结算 3-失败',
    create_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    update_time     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_batch_no (batch_no),
    KEY idx_merchant_date (merchant_id, settle_date)
) ENGINE=InnoDB COMMENT='结算单';
```

### 16.4 结算流程

```
XXL-Job 每日 00:30 执行 T+1 结算：

  1. 查询昨日所有 PAID 订单，按 merchantId 分组
  2. 每商户生成一张 settle_batch
  3. 复式记账：
     for each order:
       借：应付商户  amount
       贷：商户余额  amount-fee
       贷：手续费收入 fee
  4. 更新 pay_account：
     balance += net_amount
     in_transit -= total_amount
     （乐观锁 version 控制）
  5. 自动发起银行转账（调用银企直连 API）
  6. 转账成功 → settle_batch.status = 已结算
  7. 转账失败 → settle_batch.status = 失败 → 告警 → 人工处理
```

---

## 十七、核心接口与类签名设计

以下为可直接落地实现的 Java 接口定义，与现有代码体系对齐。

### 17.1 PaymentFacade

```java
package com.joker.spzx.manager.facade;

@Service
public class PaymentFacade {

    // ===== 统一下单 =====
    public PayCreateVO createPayment(PayCreateDTO dto) {
        // 1. 幂等校验
        // 2. 分布式锁
        // 3. 事前风控
        // 4. 状态机校验
        // 5. 智能路由
        // 6. 策略分发
        // 7. 持久化
        // 8. 事件发布
    }

    // ===== 统一回调处理 =====
    public PayNotifyResult handleNotify(String channel, String body) {
        // 1. 回调处理器分发（解析+验签+转换）
        // 2. 幂等校验
        // 3. 分布式锁
        // 4. 状态机流转
        // 5. 更新订单
        // 6. 事件发布
    }

    // ===== 统一退款 =====
    public void refund(RefundCreateDTO dto) {
        // 1. 幂等校验
        // 2. 分布式锁
        // 3. 退款风控
        // 4. 原单校验（已支付 + 退款金额 <= 原金额 - 已退金额）
        // 5. 策略分发
        // 6. 持久化退款单
        // 7. 事件发布
    }

    // ===== 查询订单 =====
    public PayQueryVO queryPayment(String orderNo) { ... }

    // ===== 关闭订单 =====
    public void closePayment(String orderNo) { ... }
}
```

### 17.2 状态机

```java
package com.joker.spzx.manager.domain.state;

// 支付订单状态机
@Component
public class PaymentStateMachine {

    private static final Map<PaymentStatusEnum, Set<PaymentStatusEnum>> TRANSITIONS = Map.of(
        UNPAID,    Set.of(PAYING, CLOSED),
        PAYING,    Set.of(PAID, PAY_ERROR, CLOSED),
        PAID,      Set.of(REFUNDING),
        REFUNDING, Set.of(PAID, REFUNDED, REFUND_FAILED),  // 部分退款仍为PAID
        REFUNDED,  Set.of(),  // 终态
        PAY_ERROR, Set.of(PAYING),  // 允许重试
        CLOSED,    Set.of()   // 终态
    );

    public void checkTransition(PaymentStatusEnum from, PaymentStatusEnum to) {
        Set<PaymentStatusEnum> allowed = TRANSITIONS.getOrDefault(from, Set.of());
        if (!allowed.contains(to)) {
            throw new PayStateException(
                "非法状态流转: " + from + " → " + to);
        }
    }
}

// 退款单状态机
@Component
public class RefundStateMachine {

    private static final Map<RefundStatusEnum, Set<RefundStatusEnum>> TRANSITIONS = Map.of(
        REFUND_PENDING,    Set.of(REFUND_PROCESSING, REFUND_FAILED),
        REFUND_PROCESSING, Set.of(REFUND_SUCCESS, REFUND_FAILED),
        REFUND_SUCCESS,    Set.of(),  // 终态
        REFUND_FAILED,     Set.of(REFUND_PENDING)  // 允许重试
    );
}
```

### 17.3 幂等服务

```java
package com.joker.spzx.manager.service;

@Service
public class IdempotentService {

    @Autowired
    private StringRedisTemplate redis;

    /**
     * 幂等检查 + 结果缓存
     * @param key 幂等键 (如 pay:idempotent:{orderNo})
     * @param ttl 过期时间
     * @return true=首次请求, false=重复请求
     */
    public boolean acquire(String key, Duration ttl) {
        Boolean result = redis.opsForValue().setIfAbsent(key, "1", ttl);
        return Boolean.TRUE.equals(result);
    }

    /**
     * 缓存首次请求的结果（供重复请求返回）
     */
    public void cacheResult(String key, Object result, Duration ttl) {
        redis.opsForValue().set(key, JSON.toJSONString(result), ttl);
    }

    /**
     * 获取缓存的首次请求结果
     */
    public <T> T getCachedResult(String key, Class<T> clazz) {
        String json = redis.opsForValue().get(key);
        return json != null ? JSON.parseObject(json, clazz) : null;
    }
}
```

### 17.4 渠道回调处理器

```java
package com.joker.spzx.manager.pay.handler;

// 统一回调处理器接口
public interface ChannelNotifyHandler {

    String getChannel();  // "wechat" / "alipay" / "stripe" / ...

    /**
     * 解析 + 验签 + 转换为标准结果
     * @return PayNotifyResult（标准化）
     */
    PayNotifyResult parseAndVerify(String body, HttpServletRequest request);

    /**
     * 渠道要求的成功响应
     */
    String successResponse();

    /**
     * 渠道要求的失败响应
     */
    String failResponse();
}

// 处理器工厂
@Component
public class NotifyHandlerFactory {

    private final Map<String, ChannelNotifyHandler> handlerMap;

    public NotifyHandlerFactory(List<ChannelNotifyHandler> handlers) {
        this.handlerMap = handlers.stream()
            .collect(Collectors.toMap(
                ChannelNotifyHandler::getChannel, Function.identity()));
    }

    public ChannelNotifyHandler getHandler(String channel) {
        ChannelNotifyHandler handler = handlerMap.get(channel);
        if (handler == null) {
            throw new IllegalArgumentException("不支持的回调渠道: " + channel);
        }
        return handler;
    }
}
```

### 17.5 智能路由

```java
package com.joker.spzx.manager.pay.strategy;

@Component
public class ChannelRouter {

    @Autowired private PayStrategyFactory strategyFactory;
    @Autowired private MerchantChannelDomainService merchantChannelService;
    @Autowired private ChannelHealthService healthService;

    /**
     * 智能路由：从商户可用渠道中选择最优支付方式
     */
    public PayTypeEnum route(PayCreateDTO dto) {
        Long merchantId = dto.getMerchantId();

        // 1. 获取商户可用渠道列表（Caffeine 缓存）
        List<MerchantChannel> channels = merchantChannelService
            .getAvailableChannels(merchantId);

        // 2. 过滤：渠道健康 + 限额 + 支持该 payType
        List<MerchantChannel> candidates = channels.stream()
            .filter(c -> healthService.isHealthy(c.getChannel()))
            .filter(c -> c.supportsPayType(dto.getPayType()))
            .filter(c -> c.withinDailyLimit())
            .sorted(Comparator.comparing(MerchantChannel::getPriority))
            .toList();

        if (candidates.isEmpty()) {
            throw new PayException("无可用支付渠道");
        }

        // 3. Sentinel 限流检查（逐渠道尝试）
        for (MerchantChannel candidate : candidates) {
            if (sentinelPass(candidate.getChannel())) {
                return dto.getPayType();
            }
        }

        // 4. 全部限流 → 返回最低优先级渠道（兜底）
        return candidates.get(candidates.size() - 1).getPayType();
    }

    private boolean sentinelPass(String channel) {
        try (Entry entry = SphU.entry("channelCall:" + channel)) {
            return true;
        } catch (BlockException e) {
            return false;
        }
    }
}
```

### 17.6 分布式锁封装

```java
package com.joker.spzx.manager.service;

@Service
public class DistributedLockService {

    @Autowired
    private RedissonClient redisson;

    /**
     * 执行带分布式锁的操作
     * @param lockKey  锁键
     * @param waitTime 等待获取锁的最大时间
     * @param leaseTime 持有锁的最大时间
     */
    public <T> T executeWithLock(String lockKey, Duration waitTime,
                                  Duration leaseTime, Supplier<T> action) {
        RLock lock = redisson.getLock(lockKey);
        boolean acquired = false;
        try {
            acquired = lock.tryLock(waitTime.toMillis(), leaseTime.toMillis(), TimeUnit.MILLISECONDS);
            if (!acquired) {
                throw new PayException("操作正在处理中，请勿重复提交: " + lockKey);
            }
            return action.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new PayException("获取锁被中断: " + lockKey);
        } finally {
            if (acquired && lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

### 17.7 错误码体系

```java
package com.joker.spzx.model.enums.pay;

@Getter
@AllArgsConstructor
public enum PayErrorCode {

    // ===== 通用 (PAY-0xxx) =====
    SUCCESS              ("PAY-0000", "成功"),
    SYSTEM_ERROR         ("PAY-0001", "系统异常"),
    PARAM_INVALID        ("PAY-0002", "参数校验失败"),

    // ===== 下单 (PAY-1xxx) =====
    ORDER_EXISTS         ("PAY-1001", "订单已存在，请勿重复下单"),
    ORDER_PROCESSING     ("PAY-1002", "订单正在处理中"),
    ORDER_STATUS_INVALID ("PAY-1003", "订单状态不允许此操作"),
    AMOUNT_INVALID       ("PAY-1004", "支付金额必须大于0"),
    MERCHANT_NOT_FOUND   ("PAY-1005", "商户不存在或已禁用"),
    CHANNEL_UNAVAILABLE  ("PAY-1006", "支付渠道暂不可用"),
    NO_AVAILABLE_CHANNEL ("PAY-1007", "无可用支付渠道"),

    // ===== 回调 (PAY-2xxx) =====
    NOTIFY_SIGN_FAIL     ("PAY-2001", "回调验签失败"),
    NOTIFY_ORDER_NOT_FOUND("PAY-2002", "回调订单不存在"),
    NOTIFY_DUPLICATE     ("PAY-2003", "重复回调，幂等处理"),
    NOTIFY_PARSE_FAIL    ("PAY-2004", "回调数据解析失败"),

    // ===== 退款 (PAY-3xxx) =====
    REFUND_EXCEED        ("PAY-3001", "退款金额超过可退金额"),
    REFUND_ORDER_NOT_PAID("PAY-3002", "原订单未支付，不可退款"),
    REFUND_DUPLICATE     ("PAY-3003", "退款单已存在"),
    REFUND_RETRY_EXCEED  ("PAY-3004", "退款重试次数超限，需人工处理"),

    // ===== 风控 (PAY-4xxx) =====
    RISK_REJECT          ("PAY-4001", "风控拦截"),
    RISK_REVIEW          ("PAY-4002", "风控审核中"),
    MERCHANT_LIMIT_EXCEED("PAY-4003", "商户交易限额超出"),

    // ===== 渠道 (PAY-5xxx) =====
    CHANNEL_CALL_FAIL    ("PAY-5001", "渠道调用失败"),
    CHANNEL_TIMEOUT      ("PAY-5002", "渠道调用超时"),
    CHANNEL_CIRCUIT_OPEN ("PAY-5003", "渠道熔断中，请稍后重试"),

    // ===== 对账 (PAY-6xxx) =====
    RECONCILE_DIFF_FOUND ("PAY-6001", "对账差异已记录"),
    RECONCILE_BATCH_FAIL ("PAY-6002", "对账批次执行失败");

    private final String code;
    private final String message;
}
```

---

## 十八、核心流程时序图

### 18.1 统一下单时序

```
商家系统          Gateway        PayV2Controller    PaymentFacade    ChannelRouter    PayStrategy    PaymentOrderService    RocketMQ
   │                 │                │                 │                │               │               │                  │
   │── POST /create ──→│                │                 │                │               │               │                  │
   │                 │── 转发 ──────→│                 │                │               │               │                  │
   │                 │                │── createPayment ─→│                │               │               │                  │
   │                 │                │                 │── 幂等校验(Redis) ──────────────────────────────────────────────→│
   │                 │                │                 │← 幂等通过 ─────────────────────────────────────────────────────│
   │                 │                │                 │── 分布式锁(Redisson) ──────────────────────────────────────────→│
   │                 │                │                 │── 事前风控 ─────→│               │               │                  │
   │                 │                │                 │← 风控通过 ──────│               │               │                  │
   │                 │                │                 │── 状态机校验 ───→│               │               │                  │
   │                 │                │                 │── route() ──────→│               │               │                  │
   │                 │                │                 │← 选定 payType ──│               │               │                  │
   │                 │                │                 │── createPayment(payType) ──→│               │               │                  │
   │                 │                │                 │                │               │── 调渠道SDK ──→│               │                  │
   │                 │                │                 │                │               │← prepayId ────│               │                  │
   │                 │                │                 │← PayCreateVO ──────────────────────────────────│               │                  │
   │                 │                │                 │── save() ──────────────────────────────────────→│               │                  │
   │                 │                │                 │── 事务消息 ──────────────────────────────────────────────────────→│
   │                 │                │                 │← 完成 ─────────────────────────────────────────────────────────│
   │                 │                │← PayCreateVO ───│                │               │               │                  │
   │                 │← Result ───────│                 │                │               │               │                  │
   │← HTTP 200 ──────│                │                 │                │               │               │                  │
```

### 18.2 支付回调时序

```
渠道             NotifyController    NotifyHandlerFactory   ChannelNotifyHandler   PaymentFacade    PaymentOrderService    RocketMQ
  │                  │                    │                      │                    │                  │                  │
  │── POST /notify/wechat ──→│            │                      │                    │                  │                  │
  │                  │── getHandler("wechat") ─→│                 │                    │                  │                  │
  │                  │← handler ──────────│                      │                    │                  │                  │
  │                  │── parseAndVerify(body) ──────────────────→│                    │                  │                  │
  │                  │                   │                      │── 验签+解析 ─────→│                    │                  │                  │
  │                  │← PayNotifyResult ────────────────────────│                    │                  │                  │
  │                  │── handleNotify(result) ──────────────────────────────────────→│                  │                  │
  │                  │                   │                      │                    │── 幂等校验(Redis) ──────────────────→│                  │
  │                  │                   │                      │                    │← 首次回调 ─────────────────────────│                  │
  │                  │                   │                      │                    │── 分布式锁 ──────────────────────→│                  │
  │                  │                   │                      │                    │── 状态机: PAYING→PAID ───────────→│                  │
  │                  │                   │                      │                    │── markPaid() ─────────────────────→│                  │
  │                  │                   │                      │                    │← 更新成功 ────────────────────────│                  │
  │                  │                   │                      │                    │── 发送 pay.success ───────────────────────────────────────→│
  │                  │                   │                      │                    │← 完成 ───────────────────────────────────────────────────│
  │                  │← success ─────────────────────────────────────────────────────│                  │                  │
  │← XML SUCCESS ────│                    │                      │                    │                  │                  │
  │                  │                    │                      │                    │                  │                  │
  │                  │  [异步] MerchantNotifyConsumer ←── pay.success ──────────────────────────────────────────────────────│
  │                  │  [异步] AccountingConsumer     ←── pay.success ──────────────────────────────────────────────────────│
  │                  │  [异步] RiskControlConsumer    ←── pay.success ──────────────────────────────────────────────────────│
```

### 18.3 退款时序

```
商家系统       PayV2Controller    PaymentFacade    PayStrategy    RefundOrderService    PaymentOrderService    RocketMQ
   │                │                 │               │                  │                     │                  │
   │── POST /refund ─→│                │               │                  │                     │                  │
   │                │── refund(dto) ──→│               │                  │                     │                  │
   │                │                 │── 幂等校验 ───────────────────────────────────────────────────────────────→│
   │                │                 │── 分布式锁 ───────────────────────────────────────────────────────────────→│
   │                │                 │── 原单校验(已支付+可退金额) ──────────────────────────────────────────────→│
   │                │                 │← 校验通过 ─────────────────────────────────────────────────────────────────│
   │                │                 │── 保存退款单(PENDING) ──→│                     │                     │                  │
   │                │                 │── refund() ──────────→│                     │                     │                  │
   │                │                 │               │── 调渠道退款API ──→│                     │                     │                  │
   │                │                 │               │← 退款受理 ─────────│                     │                     │                  │
   │                │                 │← 退款已提交 ──────────│                     │                     │                  │
   │                │                 │── 更新退款单(PROCESSING) ─→│                     │                     │                  │
   │                │                 │── 更新原单(REFUNDING) ────────────────────────────────────────────────────→│                  │
   │                │                 │── 发送 refund.requested ───────────────────────────────────────────────────────────────────────→│
   │                │← Result ────────│               │                  │                     │                  │
   │← HTTP 200 ─────│                 │               │                  │                     │                  │
   │                │                 │               │                  │                     │                  │
   │  [异步] 渠道退款回调 → NotifyController → PaymentFacade.handleRefundNotify()                     │                  │
   │                │                 │── 更新退款单(SUCCESS) ─→│                     │                     │                  │
   │                │                 │── 更新原单(REFUNDED/PARTIAL_REFUND) ─────────────────────────────────────→│                  │
   │                │                 │── 发送 refund.success ───────────────────────────────────────────────────────────────────────→│
   │                │                 │  [异步] 通知商家 + 记账 + 风控                                                    │                  │
```

### 18.4 T+1 对账时序

```
XXL-Job         ReconcileService    ChannelSDK      reconcile_detail    PaymentOrderService    RocketMQ
   │                │                    │                  │                     │                  │
   │── execute ────→│                    │                  │                     │                  │
   │                │── 下载渠道账单 ────→│                  │                     │                  │
   │                │← 账单文件 ──────────│                  │                     │                  │
   │                │── 解析账单 → 写入 ──────────────────→│                     │                  │
   │                │── 查询平台当日订单 ──────────────────────────────────────────→│                  │
   │                │← payment_order 列表 ─────────────────────────────────────────│                  │
   │                │── 逐笔比对 ─────────│                  │                     │                  │
   │                │  for each record:   │                  │                     │                  │
   │                │    平台 vs 渠道     │                  │                     │                  │
   │                │    差异分类 ────────│────────────────→│                     │                  │
   │                │── 统计差异 ─────────│                  │                     │                  │
   │                │── if diff > 0: ────│──────────────────────────────────────────────────────────────→│
   │                │    发送 reconcile.diff 事件 ───────────────────────────────────────────────────────→│
   │                │    [异步] 告警 + 人工处理 ────────────────────────────────────────────────────────→│
   │← 完成 ─────────│                    │                  │                     │                  │
```

---

## 十九、异常场景与补偿策略矩阵

| 异常场景 | 发生时机 | 影响 | 检测方式 | 补偿策略 | 优先级 |
|----------|----------|------|----------|----------|--------|
| 渠道下单超时 | createPayment | 订单可能已创建 | 超时 + 查询确认 | 查询渠道→已创建则关单→返回失败；未创建则重试 | P1 |
| 渠道下单成功但本地事务回滚 | createPayment | 渠道有单、本地无单 | 事务消息回查 | 回查发现本地无记录→rollback MQ→定时关渠道单 | P1 |
| 回调到达但订单不存在 | handleNotify | 渠道有单、本地无单 | 查询 payment_order | 记录异常日志→查询渠道确认→补单或告警 | P2 |
| 回调重复到达 | handleNotify | 重复处理风险 | Redis 幂等键 | 幂等返回 SUCCESS | P1 |
| 回调后 MQ 发送失败 | handleNotify | 商家收不到通知 | MQ 发送异常 | 本地事务表 + 定时扫描重发 | P1 |
| 退款调用渠道失败 | refund | 退款未执行 | 渠道返回错误 | 更新状态为 FAILED→XXL-Job 重试3次→人工 | P1 |
| 退款回调未到达 | refund | 退款状态不更新 | 超时未回调 | XXL-Job 每10min 查询渠道退款状态→更新 | P2 |
| 渠道对账单下载失败 | reconcile | 无法对账 | 下载异常 | 重试3次→告警→人工下载→导入 | P2 |
| 对账差异 | reconcile | 资金不一致 | 逐笔比对 | 差异记录→告警→人工核查→调账 | P1 |
| 商户回调地址不可达 | notify | 商家收不到通知 | HTTP 调用失败 | 15次重试(指数退避)→标记失败→告警 | P2 |
| Redis 宕计锁宕机 | createPayment | 并发下单风险 | Redisson 检测 | 锁自动释放(leaseTime)→DB 唯一索引兜底 | P1 |
| MySQL 主从延迟 | queryPayment | 查到旧状态 | 读写分离延迟 | 支付查询强制走主库 | P2 |
| 渠道密钥过期 | channelCall | 全渠道失败 | 渠道返回鉴权失败 | 告警→Nacos 热更新密钥→自动恢复 | P1 |
| 分库分表路由热点 | createPayment | 单分片过载 | 监控分片流量 | 哈希打散→动态扩容分片 | P3 |
| MQ 消费积压 | 所有异步 | 延迟增大 | MQ 积压监控 | 增加消费者→扩容→死信处理 | P2 |
| 风控误拦 | createPayment | 正常订单被拒 | 风控命中记录 | 人工复核→加白名单→调整规则 | P3 |

---

## 二十、分库分表键设计修正

### 20.1 原方案问题

```
原方案：merchant_id 分库 + order_no 分表
问题：
  1. 大商户（merchant_id 固定）所有订单落入同一库 → 单库热点
  2. 冷热数据混杂：历史订单和当日订单在同一分片 → 查询效率下降
  3. 跨商户查询（运营后台）需要全库扫描
```

### 20.2 修正方案

```
分库：order_no 的 hash 取模（16库）
  → 订单均匀分布，无大商户热点
  → 同一 orderNo 精准路由到单库单表

分表：order_no 的 hash 取模（每库4表）
  → 16库 × 4表 = 64个物理表（初期足够，可动态扩容）

冷热分离：
  payment_order（热数据）：仅存最近90天订单，按 order_no 分库分表
  payment_order_archive（冷数据）：90天前订单，按 create_time 月度归档
  → XXL-Job 每日迁移过期数据到归档表

商户维度查询：
  → idx_merchant_status(merchant_id, status) 索引 + ShardingSphere 广播查询
  → 大商户查询走 ClickHouse 预计算结果（不走 MySQL）

分片扩容：
  ShardingSphere 5.5.x 支持在线扩容
  16库 → 32库：一致性哈希迁移，无需停机
```

### 20.3 ShardingSphere 配置骨架

```yaml
sharding-sphere:
  datasource:
    names: ds0,ds1,...,ds15
    # 16个 MySQL 数据源

  sharding:
    tables:
      payment_order:
        actual-data-nodes: ds${0..15}.payment_order_${0..3}
        database-strategy:
          standard:
            sharding-column: order_no
            sharding-algorithm-name: order_no_db_algo
        table-strategy:
          standard:
            sharding-column: order_no
            sharding-algorithm-name: order_no_table_algo
        key-generate-strategy:
          column: id
          key-generator-name: snowflake

      refund_order:
        actual-data-nodes: ds${0..15}.refund_order_${0..3}
        # 同 payment_order

    broadcast-tables:
      - merchant_channel_config
      - pay_channel_config
      - pay_merchant
      - risk_rule
      - risk_blacklist

    sharding-algorithms:
      order_no_db_algo:
        type: HASH_MOD
        props:
          sharding-count: 16
      order_no_table_algo:
        type: HASH_MOD
        props:
          sharding-count: 4

    key-generators:
      snowflake:
        type: SNOWFLAKE
        props:
          worker-id: ${random.int[0,1023]}

  readwrite-splitting:
    data-sources:
      ds0:
        write-data-source-name: ds0_master
        read-data-source-names: ds0_slave0,ds0_slave1
        load-balancer-name: round_robin
      # ds1 ~ ds15 同理
```

---

## 二十一、状态机增强：部分退款与多次退款

### 21.1 增强后的支付状态机

```
UNPAID ──create──→ PAYING ──notify.success──→ PAID
  │                   │                        │
  │                   ├── notify.fail ──→ PAY_ERROR ──retry──→ PAYING
  │                   ├── close/timeout ─→ CLOSED
  │                   │
  │                   │             ┌── 全额退款 ──→ REFUNDED (终态)
  │                   │             │
  │                   └── refund ──→ PARTIAL_REFUNDED
  │                                 │   │
  │                                 │   ├── 再次退款(仍部分) ──→ PARTIAL_REFUNDED
  │                                 │   │
  │                                 │   └── 最后一笔退款(全额) ──→ REFUNDED (终态)
  │                                 │
  │                                 └── 退款失败 ──→ PAID (恢复，可重试)
  │
  └── cancel ──→ CLOSED
```

### 21.2 退款金额校验逻辑

```java
// PaymentOrder 聚合根内
public void validateRefund(BigDecimal refundAmount) {
    if (status != PAID && status != PARTIAL_REFUNDED) {
        throw new PayException(PayErrorCode.ORDER_STATUS_INVALID);
    }
    BigDecimal refunded = getRefundedAmount();  // 已退款总额
    BigDecimal refundable = amount.subtract(refunded);
    if (refundAmount.compareTo(refundable) > 0) {
        throw new PayException(PayErrorCode.REFUND_EXCEED);
    }
}

public void applyRefund(BigDecimal refundAmount) {
    validateRefund(refundAmount);
    this.refundedAmount = this.refundedAmount.add(refundAmount);
    if (this.refundedAmount.compareTo(this.amount) == 0) {
        this.status = REFUNDED;        // 全额退款
    } else {
        this.status = PARTIAL_REFUNDED; // 部分退款
    }
}
```

### 21.3 增强的 PaymentStatusEnum

```java
public enum PaymentStatusEnum {
    UNPAID(0, "未支付"),
    PAYING(1, "支付中"),
    PAID(2, "已支付"),
    PARTIAL_REFUNDED(3, "部分退款"),   // 【新增】
    REFUNDING(4, "退款中"),
    REFUNDED(5, "已退款"),
    REFUND_FAILED(6, "退款失败"),      // 【新增】
    PAY_ERROR(7, "支付失败"),
    CLOSED(8, "已关闭");
}
```

---

## 二十二、RocketMQ 事务消息实现细节

### 22.1 事务消息流程

```java
// 生产者：下单时发送事务消息
@Service
public class PayEventProducer {

    @Autowired
    private TransactionMQProducer producer;

    public void sendPayCreatedEvent(PaymentOrder order) {
        Message msg = new Message(
            "pay_topic",
            "pay.created",
            JSON.toJSONString(order).getBytes()
        );
        // 发送事务消息
        producer.sendMessageInTransaction(msg, order);
    }
}

// 事务监听器：执行本地事务 + 回查
@Component
@RocketMQTransactionListener
public class PayTransactionListener implements TransactionListener {

    @Autowired
    private PaymentOrderService orderService;

    // 执行本地事务
    @Override
    public LocalTransactionState executeLocalTransaction(Message msg, Object arg) {
        PaymentOrder order = (PaymentOrder) arg;
        try {
            orderService.save(order);  // 保存订单到 DB
            return LocalTransactionState.COMMIT_MESSAGE;
        } catch (Exception e) {
            return LocalTransactionState.ROLLBACK_MESSAGE;
        }
    }

    // 事务回查（MQ broker 主动调用）
    @Override
    public LocalTransactionState checkLocalTransaction(MessageExt msg) {
        PaymentOrder order = JSON.parseObject(
            msg.getBody(), PaymentOrder.class);
        // 查 DB 看订单是否存在
        boolean exists = orderService.existsByOrderNo(order.getOrderNo());
        return exists
            ? LocalTransactionState.COMMIT_MESSAGE
            : LocalTransactionState.ROLLBACK_MESSAGE;
    }
}
```

### 22.2 消费者幂等

```java
@Component
@RocketMQMessageListener(
    topic = "pay_topic",
    consumerGroup = "merchant_notify_group",
    selectorExpression = "pay.success || refund.success"
)
public class MerchantNotifyConsumer implements RocketMQListener<MessageExt> {

    @Autowired private IdempotentService idempotentService;
    @Autowired private MerchantNotifyService notifyService;

    @Override
    public void onMessage(MessageExt message) {
        String msgKey = message.getKeys();  // orderNo
        String idempotentKey = "mq:consumed:" + message.getTopic() + ":" + msgKey;

        // 幂等检查
        if (!idempotentService.acquire(idempotentKey, Duration.ofDays(7))) {
            return;  // 已消费，跳过
        }

        // 处理消息
        PaySuccessEvent event = JSON.parseObject(
            message.getBody(), PaySuccessEvent.class);
        notifyService.notifyMerchant(event);
    }
}
```

### 22.3 Topic 与 Tag 规划

```
Topic: pay_topic
  Tags:
    pay.created       — 下单成功
    pay.success       — 支付成功
    pay.failed        — 支付失败
    pay.closed        — 订单关闭
    refund.requested  — 退款发起
    refund.success    — 退款成功
    refund.failed     — 退款失败
    reconcile.diff    — 对账差异

Topic: pay_notify_topic（商户通知，独立 Topic 避免互相影响）
  Tags:
    notify.pay        — 支付通知
    notify.refund     — 退款通知

消费组规划：
  merchant_notify_group   — 商户通知（顺序消费）
  accounting_group        — 记账（普通消费）
  risk_control_group      — 风控（普通消费）
  reconcile_prep_group    — 对账预备（普通消费）
```

---

## 二十三、容量规划与压测方案

### 23.1 容量规划

```
假设业务目标：
  日交易量 100万笔
  峰值 QPS 2000（下单）/ 5000（回调）
  商户数 1000+

存储规划：
  payment_order：100万/天 × 365天 = 3.65亿/年
    单行约 500B → 3.65亿 × 500B ≈ 180GB/年
    16库 × 4表 = 64分片 → 每分片 ≈ 2.8GB/年
    90天热数据：每分片 ≈ 700MB → 完全在 InnoDB buffer pool

  pay_trade_record：100万/天 × 2（支付+查询）= 200万/天
    90天 ≈ 1.8亿条 → 每分片 ≈ 1.4GB

  reconcile_detail：100万/天
    365天 ≈ 3.65亿条 → 单表即可（按月分表）

Redis 规划：
  幂等键：100万/天 × 500B × 7天 ≈ 3.5GB
  分布式锁：瞬时并发 5000 × 200B ≈ 1MB
  缓存：商户配置 1000 × 2KB ≈ 2MB
  总计：4GB → 部署 8GB Redis Cluster（3主3从）

RocketMQ 规划：
  日消息量：100万 × 4（created+success+notify+accounting）= 400万/天
  峰值：5000 QPS × 4 = 20000 msg/s
  存储：400万 × 1KB × 7天 ≈ 28GB
  → 3 Broker，每 Broker 100GB 磁盘
```

### 23.2 压测方案

```
工具：JMeter 5.x + Grafana 监控

场景1：下单压测
  目标：2000 QPS，P99 < 200ms
  数据：10万商户 × 随机金额 1-1000元
  观察：
    - 渠道 SDK 调用 RT（Mock 渠道，避免真实渠道限频）
    - DB 写入 RT
    - Redis 幂等 + 锁 RT
    - MQ 发送 RT
    - 错误率 = 0

场景2：回调压测
  目标：5000 QPS，P99 < 50ms
  数据：模拟渠道回调请求
  观察：
    - 回调处理 RT（应 < 50ms）
    - MQ 发送 RT
    - 幂等命中率（重复回调比例）

场景3：并发幂等
  目标：同一 orderNo 并发 100 次下单
  预期：1 次成功，99 次幂等返回
  观察：DB 无重复记录

场景4：渠道降级
  操作：压测中模拟渠道超时
  预期：Sentinel 熔断 → ChannelRouter 切换备用渠道
  观察：降级耗时 < 1s

场景5：MQ 积压
  操作：停止消费者，持续发送 10万消息，恢复消费者
  预期：消费者追平，无消息丢失
  观察：追平耗时 + 幂等消费正确性

场景6：分布式锁竞争
  操作：100线程同时获取同一 orderNo 的锁
  预期：1 个成功，99 个抛异常
  观察：锁等待时间 < 3s
```

### 23.3 滑动窗口成功率统计

```java
// 渠道成功率实时统计（用于智能路由）
@Component
public class ChannelSuccessRateTracker {

    @Autowired
    private StringRedisTemplate redis;

    // 滑动窗口：1分钟，10个桶（每6秒一个桶）
    private static final int WINDOW_SECONDS = 60;
    private static final int BUCKET_COUNT = 10;
    private static final int BUCKET_SECONDS = WINDOW_SECONDS / BUCKET_COUNT;

    public void record(String channel, boolean success) {
        long now = System.currentTimeMillis() / 1000;
        int bucket = (int) ((now / BUCKET_SECONDS) % BUCKET_COUNT);
        String key = "pay:rate:" + channel + ":" + bucket;
        redis.opsForHash().increment(key, success ? "success" : "fail", 1);
        redis.expire(key, WINDOW_SECONDS + 10, TimeUnit.SECONDS);
    }

    public double getSuccessRate(String channel) {
        long success = 0, total = 0;
        for (int i = 0; i < BUCKET_COUNT; i++) {
            String key = "pay:rate:" + channel + ":" + i;
            Map<Object, Object> bucket = redis.opsForHash().entries(key);
            success += Long.parseLong(bucket.getOrDefault("success", "0").toString());
            total += Long.parseLong(bucket.getOrDefault("success", "0").toString())
                   + Long.parseLong(bucket.getOrDefault("fail", "0").toString());
        }
        return total == 0 ? 1.0 : (double) success / total;
    }
}
```

---

## 二十四、灰度发布策略

### 24.1 v1 → v2 切流

```
Gateway 层灰度路由（基于请求头/商户ID）：

阶段1（1周）：影子流量
  - 复制 v1 请求到 v2（不影响真实业务）
  - 对比 v1/v2 响应，验证一致性
  - v2 异常不影响用户

阶段2（1周）：10% 商户灰度
  - merchantId % 100 < 10 → 走 v2
  - 其余 → 走 v1
  - 监控 v2 错误率、RT、成功率

阶段3（1周）：50% 商户灰度
  - merchantId % 100 < 50 → 走 v2
  - 其余 → 走 v1

阶段4（1周）：100% 切流
  - 全部走 v2
  - v1 保留但标记 @Deprecated

阶段5（30天后）：v1 下线
  - v2 稳定运行 30 天无 P1 故障
  - 删除 v1 代码
```

### 24.2 灰度配置

```yaml
# Nacos 动态配置
pay:
  grayscale:
    enabled: true
    v2-ratio: 10          # v2 流量比例 0-100
    v2-merchant-whitelist: []  # 强制走 v2 的商户ID
    v1-merchant-whitelist: []  # 强制走 v1 的商户ID（白名单保底）
```

```java
// Gateway 灰度过滤器
@Component
public class PayGrayscaleFilter implements GlobalFilter {

    @Value("${pay.grayscale.v2-ratio:0}")
    private int v2Ratio;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getURI().getPath();
        if (!path.startsWith("/api/pay/")) {
            return chain.filter(exchange);
        }

        Long merchantId = extractMerchantId(exchange);
        boolean useV2 = merchantId % 100 < v2Ratio;

        String targetPath = useV2
            ? path.replace("/api/pay/", "/api/v2/pay/")
            : path;

        ServerHttpRequest request = exchange.getRequest().mutate()
            .path(targetPath).build();
        return chain.filter(exchange.mutate().request(request).build());
    }
}
```

---

## 二十五、部署与容灾

### 25.1 部署架构

```
K8s 部署（namespace: payment）

  ├── pay-api (3副本, NodePort)
  │     ├── Pod1: pay-api + JDK21 虚拟线程
  │     ├── Pod2
  │     └── Pod3
  │     HPA: CPU > 70% 扩容，min=3 max=10
  │
  ├── pay-consumer (2副本)
  │     ├── Pod1: MQ 消费者（通知/记账/风控）
  │     └── Pod2
  │
  ├── pay-job (1副本)
  │     └── Pod1: XXL-Job 执行器（对账/关单/重试）
  │
  └── pay-admin (1副本)
        └── Pod1: 管理后台（对账查看/商户管理/风控配置）

中间件（namespace: middleware）：
  ├── redis-cluster (6节点: 3主3从)
  ├── rocketmq (3 Broker + namesrv)
  └── mysql (16主 + 16从)
```

### 25.2 容灾策略

```
应用层：
  - 3 副本部署，单 Pod 故障自动重启
  - 优雅停机：Spring Boot graceful shutdown，等待处理中请求完成
  - 就绪探针：检查 Redis + MQ + DB 连通性

数据层：
  - MySQL：主从半同步复制，主挂自动切从
  - Redis：Cluster 模式，自动 failover
  - RocketMQ：3 Broker，单挂不影响消息收发

渠道层：
  - 渠道不可用 → ChannelRouter 自动降级
  - 渠道密钥过期 → Nacos 热更新

跨可用区：
  - 2 AZ 部署，同城双活
  - MySQL 跨 AZ 主从
  - Redis 跨 AZ 部署
```

### 25.3 优雅停机

```yaml
server:
  shutdown: graceful          # 等待处理中请求完成
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # 最大等待30s
  threads:
    virtual:
      enabled: true           # JDK21 虚拟线程
```

```java
// 停机时拒绝新请求，等待旧请求完成
@PreDestroy
public void onShutdown() {
    // 1. 标记服务为不可用（健康检查返回 DOWN）
    // 2. 等待 MQ 消费完成（最长30s）
    // 3. 释放所有分布式锁
    // 4. 关闭渠道连接池
}
```

---

## 二十六、更新后的实施路线图

```
第一阶段：补齐基础（1-2周）
  [ ] 回调白名单 + 回调持久化 + DB 唯一索引
  [ ] 修复 PayPal/Stripe/支付宝已知 bug
  [ ] PaymentInfo 字段类型修正

第二阶段：幂等 + 状态机 + 锁（2-3周）
  [ ] IdempotentService + DistributedLockService
  [ ] PaymentStateMachine（含部分退款）
  [ ] 单元测试：并发幂等 + 状态流转

第三阶段：领域模型 + v2 API + Facade（3-4周）
  [ ] PaymentOrder/RefundOrder 聚合根
  [ ] PaymentFacade 统一编排
  [ ] PayV2Controller + NotifyController
  [ ] NotifyHandlerFactory + 各渠道 Handler
  [ ] 数据迁移 + 灰度切流

第四阶段：事件驱动（4-5周）
  [ ] RocketMQ 事务消息 + 回查
  [ ] 6个事件 + 4个消费者
  [ ] MerchantNotifyRetryJob
  [ ] 顺序消费 + 幂等消费

第五阶段：风控 + 商户 + 结算（5-7周）
  [ ] RiskRuleEngine + 3层风控
  [ ] 商户注册/审核/密钥管理
  [ ] 复式记账 + T+1 结算
  [ ] 商户提现

第六阶段：高并发（7-8周）
  [ ] ShardingSphere 分库分表（修正方案：order_no 分库）
  [ ] 冷热分离 + 归档
  [ ] Caffeine + Redis 多级缓存
  [ ] Sentinel 限流熔断
  [ ] JDK21 虚拟线程

第七阶段：高可用 + 监控（8-10周）
  [ ] ChannelRouter 智能路由 + 降级
  [ ] 6个定时任务（关单/重试/对账/健康检查/结算/归档）
  [ ] Prometheus + Grafana + 告警
  [ ] 压测验证 + 容量规划
  [ ] K8s 部署 + HPA + 优雅停机
  [ ] 补齐5渠道 SDK

第八阶段：容灾 + 灰度（10-12周）
  [ ] 同城双活部署
  [ ] v1→v2 灰度切流（10%→50%→100%）
  [ ] v1 下线
  [ ] 全链路演练（渠道故障/DB主挂/MQ宕机）
```
