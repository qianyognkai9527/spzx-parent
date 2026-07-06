# 统一平台架构设计 v1.0

> 囊括所有子项目的超级平台，OAuth2 SSO 单点登录，微服务 + 微前端 + 大数据全栈

---

## 一、全局架构图（分层）

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户终端层                                │
│                         PC 门户                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                    接入层 (Edge)                                 │
│    Nginx/SLB │ CDN │ WAF防火墙 │ SSL终止                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                    网关层 (Gateway)                              │
│    Spring Cloud Gateway 4.x + Sentinel 限流熔断                  │
│    统一鉴权 │ 路由转发 │ 限流降级 │ 灰度发布 │ 日志追踪           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                  认证授权层 (Auth)                               │
│    Spring Authorization Server 1.4.x (OAuth2.1 + OIDC)          │
│    统一登录 │ Token签发 │ RBAC+ABAC权限 │ 多租户 │ 设备管理       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   微服务层 (Services)                            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │spzx-mgr │ │order-svc│ │product  │ │user-svc │ │...N个    │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│    Spring Boot 3.4 + Spring Cloud Alibaba 2023.0.1.2 + JDK 21   │
│    Nacos注册发现 │ OpenFeign/Dubbo3.3 RPC │ Sentinel熔断        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   中间件层 (Middleware)                          │
│  Redis集群 │ RocketMQ/Kafka │ XXL-Job调度 │ MinIO/OSS对象存储    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                   数据层 (Data)                                  │
│  MySQL 8.4主从 │ ShardingSphere分库分表 │ Elasticsearch搜索      │
│  Canal binlog同步 │ ClickHouse OLAP                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                 大数据层 (BigData)                               │
│  HDFS/YARN │ Flink实时计算 │ Spark离线计算 │ Hive数据仓库        │
│  DataX同步 │ DolphinScheduler │ HBase │ Kafka消息管道            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                  监控运维层 (Ops)                                │
│  SkyWalking链路 │ Prometheus+Grafana指标 │ ELK日志               │
│  K8s+Docker编排 │ Harbor镜像 │ Jenkins CI/CD │ Arthas诊断         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、技术栈选型（最新稳定版）

### 2.1 后端基础

| 组件 | 选型 | 版本 | 用途 |
|---|---|---|---|
| JDK | **Oracle/OpenJDK 21** | 21.0.5+ (LTS) | 虚拟线程、分代ZGC、模式匹配 |
| 框架 | **Spring Boot** | 3.4.x | 微服务基座 |
| 微服务 | **Spring Cloud Alibaba** | 2023.0.1.2 | 全家桶 |
| 注册中心 | **Nacos** | 2.4.x | 服务发现 + 配置中心 |
| 网关 | **Spring Cloud Gateway** | 4.2.x | 统一入口 + 鉴权 + 限流 |
| 熔断限流 | **Sentinel** | 1.8.8 | 流控 + 熔断 + 热点 + 系统自适应 |
| RPC | **OpenFeign** / **Dubbo 3.3** | — | 服务间调用（Dubbo 用于高性能场景） |
| 认证 | **Spring Authorization Server** | 1.4.x | OAuth2.1 + OIDC + JWT |

### 2.2 数据存储

| 组件 | 版本 | 用途 |
|---|---|---|
| **MySQL** | 8.4 LTS | 业务主库，主从复制 + 半同步 |
| **ShardingSphere-JDBC** | 5.5.x | 分库分表 + 读写分离 |
| **Redis** | 7.4 (Cluster) | 缓存 + 分布式锁 + 会话 |
| **Elasticsearch** | 8.17.x | 全文搜索 + 日志检索 |
| **ClickHouse** | 24.x | OLAP 分析 + 实时报表 |
| **MinIO** | 最新 | 对象存储（图片/视频/文件） |

### 2.3 消息与调度

| 组件 | 版本 | 用途 |
|---|---|---|
| **RocketMQ** | 5.3.x | 业务消息（订单/通知/事务消息） |
| **Kafka** | 3.8.x | 大数据管道（埋点/日志/实时流） |
| **XXL-Job** | 2.4.2 | 分布式定时任务调度 |
| **DolphinScheduler** | 3.2.x | 大数据任务编排（ETL/DAG） |

### 2.4 大数据

| 组件 | 版本 | 用途 |
|---|---|---|
| **HDFS + YARN** | 3.4.x | 分布式存储 + 计算资源管理 |
| **Flink** | 1.20.x | 实时流计算（实时大屏/风控/推荐） |
| **Spark** | 3.5.x | 离线批计算（T+1报表/用户画像） |
| **Hive** | 4.0.x | 数据仓库（SQL on HDFS） |
| **DataX** | 3.0.x | 异构数据同步（MySQL→Hive/ES/CK） |
| **Canal** | 1.1.8 | MySQL binlog 实时同步到 Kafka/ES |
| **HBase** | 2.6.x | 海量稀疏数据（用户行为/标签） |

### 2.5 监控运维

| 组件 | 用途 |
|---|---|
| **SkyWalking 9.x** | 全链路追踪 + 拓扑图 + 性能分析 |
| **Prometheus + Grafana** | 指标采集 + 可视化告警 |
| **ELK (Filebeat + ES + Kibana)** | 日志采集 + 检索 + 分析 |
| **Kubernetes + Docker** | 容器编排 + 自动扩缩容 |
| **Harbor** | 私有镜像仓库 |
| **Jenkins / GitLab CI** | CI/CD 流水线 |
| **Arthas** | 线上热诊断 |

### 2.6 前端

| 组件 | 版本 | 用途 |
|---|---|---|
| **Vue 3.5** | — | 门户 + 子应用基座 |
| **wujie（无界）** | 1.4.x | 微前端（iframe 沙箱，隔离最好） |
| **Element Plus** | 2.9.x | UI 组件库 |
| **ECharts / DataV** | 5.x / 2.x | 数据大屏 + 可视化 |
| **Three.js** | — | 3D 科技感门户特效 |
| **Pinia** | 2.x | 状态管理 |
| **Vite** | 5.x | 构建工具 |

---

## 三、微服务拆分

### 3.1 基础服务（平台级）

| 服务名 | 职责 | 端口 |
|---|---|---|
| `auth-center` | OAuth2 认证中心，Token 签发/校验，SSO 登录 | 8500 |
| `gateway-server` | API 网关，路由/鉴权/限流/灰度 | 8501 |
| `system-service` | 用户/角色/菜单/字典/租户管理 | 8502 |
| `file-service` | 文件上传/下载（MinIO） | 8503 |
| `notification-service` | 消息通知（短信/邮件/微信/站内信） | 8504 |
| `scheduler-admin` | XXL-Job 调度中心 | 8505 |

### 3.2 业务服务（按项目拆）

| 服务名 | 原项目 | 职责 |
|---|---|---|
| `spzx-manager-service` | spzx-parent | 商品/订单/运营管理 |
| `spzx-mall-service` | 商城 | C 端商城 |
| `order-service` | 订单系统 | 订单中心 |
| `product-service` | 商品系统 | 商品中心 |
| `user-service` | 用户系统 | 用户中心 |
| `payment-service` | 支付系统 | 支付聚合 |
| `...` | 其余项目 | 按需拆分 |

### 3.3 大数据服务

| 服务名 | 职责 |
|---|---|
| `data-collector` | 数据采集（埋点/日志/Canal） |
| `data-stream` | Flink 实时计算（实时大屏/风控） |
| `data-batch` | Spark 离线计算（T+1 报表/画像） |
| `data-api` | 数据服务（对外查询接口） |

---

## 四、OAuth2 SSO 设计

### 4.1 认证流程

```
用户 → 门户前端 → 网关 → auth-center（未登录）
  ↓ 跳转登录页
用户登录 → auth-center 签发 Authorization Code
  ↓ 回调门户
门户用 Code 换 Token → auth-center 返回 access_token + refresh_token
  ↓ Token 存储
门户请求业务服务 → 网关校验 Token → 转发到微服务
  ↓
微服务从 Token 解析用户信息 → 处理业务
```

### 4.2 Token 设计

- **access_token**：JWT，有效期 2h，包含 userId/tenantId/roles/permissions
- **refresh_token**：不透明 token，有效期 7d，存 Redis
- **Token 传递**：`Authorization: Bearer <token>`
- **网关统一校验**：Gateway 全局过滤器解析 JWT，注入用户信息到 header

### 4.3 多项目权限模型

```
租户(tenant) → 项目(project) → 角色(role) → 菜单(menu) + 权限(permission)

用户登录后:
1. auth-center 返回用户可访问的项目列表
2. 选择项目 → 加载该项目的菜单树 + 权限码
3. 前端根据菜单树渲染路由，根据权限码控制按钮
```

---

## 五、微前端设计

### 5.1 门户首页

```
┌─────────────────────────────────────────────┐
│  [Logo] 超级平台    [搜索]    [通知] [用户]  │
├─────────────────────────────────────────────┤
│                                             │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│   │ 项目1 │ │ 项目2 │ │ 项目3 │ │ 项目4 │     │
│   │ 卡片  │ │ 卡片  │ │ 卡片  │ │ 卡片  │     │
│   └──────┘ └──────┘ └──────┘ └──────┘     │
│   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│   │ 项目5 │ │ 项目6 │ │ 项目7 │ │ 项目8 │     │
│   └──────┘ └──────┘ └──────┘ └──────┘     │
│                                             │
│  [数据大屏: 实时订单/收入/用户数 ECharts]    │
└─────────────────────────────────────────────┘
```

- 暗色科技主题 + 粒子背景 + 玻璃拟态卡片 + 光晕动画
- Three.js 3D Logo / 数据流粒子效果
- 每个项目卡片：图标 + 名称 + 简介 + 状态 + 进入按钮
- 底部 ECharts 实时数据大屏（订单/收入/活跃用户）

### 5.2 微前端集成（wujie）

```
门户(Portal) ─── 主应用
  ├── wujie 加载 spzx-admin（Vue3 + ElementPlus）
  ├── wujie 加载 order-admin（Vue3 + AntDesign）
  ├── wujie 加载 data-screen（Vue3 + DataV）
  └── wujie 加载 ...N 个子应用
```

- **路由隔离**：wujie iframe 沙箱天然隔离
- **样式隔离**：子应用 CSS 不泄漏到主应用
- **通信机制**：wujie 提供 props 传递 + 事件总线
- **预加载**：空闲时预加载子应用，秒开
- **SSO 透传**：主应用 Token 通过 props 注入子应用

---

## 六、数据库设计

### 6.1 统一认证库 `db_auth`

```sql
-- 租户表
sys_tenant (id, name, code, status, expire_time)

-- 用户表（全局用户）
sys_user (id, tenant_id, username, password, phone, email, status)

-- 项目表
sys_project (id, tenant_id, name, code, icon, description, entry_url, sort)

-- 角色（按项目隔离）
sys_role (id, project_id, role_name, role_code)

-- 菜单（按项目隔离）
sys_menu (id, project_id, parent_id, title, component, icon, sort)

-- 权限码
sys_permission (id, project_id, code, name)

-- 关联表
sys_user_role (user_id, role_id)
sys_role_menu (role_id, menu_id)
sys_role_permission (role_id, permission_id)
sys_user_project (user_id, project_id) -- 用户可访问哪些项目
```

### 6.2 分库策略

| 库 | 用途 | 策略 |
|---|---|---|
| `db_auth` | 认证授权 | 单库 |
| `db_system` | 系统管理 | 单库 |
| `db_spzx` | spzx 业务 | 单库（现有） |
| `db_order` | 订单中心 | 按 tenant_id 分库 |
| `db_product` | 商品中心 | 单库 |
| `db_data` | 数据服务 | ClickHouse |
| `db_log` | 操作日志 | Elasticsearch |

---

## 七、XXL-Job 任务调度

### 7.1 调度中心

- `scheduler-admin` 独立部署，Web 界面管理
- 执行器嵌入各业务服务（引入 xxl-job-core）

### 7.2 典型任务

| 任务 | Cron | 服务 | 说明 |
|---|---|---|---|
| 订单统计 | `0 0 3 * * ?` | order-service | T+1 订单报表 |
| 退款报表 | `0 30 3 * * ?` | spzx-manager | 退款统计 |
| 数据同步 | `0 0 4 * * ?` | data-collector | MySQL → Hive (DataX) |
| 缓存预热 | `0 0 6 * * ?` | product-service | 热门商品缓存刷新 |
| Token 清理 | `0 */5 * * * ?` | auth-center | 过期 Token 清理 |
| 实时大屏 | `*/10 * * * * ?` | data-stream | Flink checkpoint |

---

## 八、大数据架构

### 8.1 数据流向

```
业务 MySQL ──Canal(binlog)──→ Kafka ──→ Flink(实时) ──→ ClickHouse(实时OLAP)
                                          ↓
                                     Elasticsearch(实时搜索)
                                          ↓
                                     Redis(实时大屏缓存)

业务 MySQL ──DataX(定时)──→ Hive(离线) ──→ Spark(批计算) ──→ MySQL(报表)
                                         ──→ HBase(用户画像)
```

### 8.2 实时链路

| 环节 | 组件 | 说明 |
|---|---|---|
| 采集 | Canal | 监听 MySQL binlog，推送到 Kafka |
| 管道 | Kafka | 消息缓冲 + 削峰 |
| 计算 | Flink | 窗口聚合/CEP 风控/实时 Join |
| 存储 | ClickHouse | 秒级 OLAP 查询 |
| 展示 | ECharts + DataV | 实时大屏 |

### 8.3 离线链路

| 环节 | 组件 | 说明 |
|---|---|---|
| 同步 | DataX | MySQL → Hive，T+1 凌晨 |
| 计算 | Spark | 用户画像/商品推荐/销售分析 |
| 仓库 | Hive | 分层：ODS → DWD → DWS → ADS |
| 调度 | DolphinScheduler | DAG 任务编排 |

---

## 九、K8s 部署架构

```
K8s 集群
├── namespace: platform        # 基础服务
│   ├── nacos (3 节点)
│   ├── gateway-server
│   ├── auth-center
│   ├── system-service
│   └── xxl-job-admin
├── namespace: business        # 业务服务
│   ├── spzx-manager (2 副本)
│   ├── order-service (2 副本)
│   └── ...
├── namespace: middleware      # 中间件
│   ├── redis-cluster (6 节点)
│   ├── rocketmq (namesrv + broker)
│   └── minio
├── namespace: monitoring      # 监控
│   ├── skywalking-oap
│   ├── prometheus
│   ├── grafana
│   └── elasticsearch
└── namespace: bigdata         # 大数据
    ├── hdfs (namenode + datanode)
    ├── flink-jobmanager
    └── flink-taskmanager
```

---

## 十、实施路线图

### 第一阶段：基建（第 1-2 周）

- [ ] 搭建 Nacos + Gateway + auth-center
- [ ] 实现 OAuth2 SSO 登录流程
- [ ] 统一用户/角色/菜单/权限模型
- [ ] spzx-manager 作为第一个子服务接入

### 第二阶段：门户（第 3-4 周）

- [ ] 奢华科技感门户首页（项目卡片墙 + 数据大屏）
- [ ] wujie 微前端集成 spzx-admin
- [ ] SSO Token 透传到子应用
- [ ] 统一暗色主题 + 玻璃拟态 UI

### 第三阶段：治理（第 5-6 周）

- [ ] Sentinel 限流熔断规则配置
- [ ] SkyWalking 全链路追踪接入
- [ ] ELK 日志采集
- [ ] Prometheus + Grafana 监控
- [ ] XXL-Job 任务调度中心

### 第四阶段：扩展（第 7-10 周）

- [ ] 逐个改造接入其余历史项目
- [ ] RocketMQ 消息总线
- [ ] Elasticsearch 搜索接入
- [ ] K8s 容器化部署 + CI/CD

### 第五阶段：大数据（第 11-14 周）

- [ ] Canal + Kafka 实时数据管道
- [ ] Flink 实时计算（大屏/风控）
- [ ] ClickHouse OLAP 分析
- [ ] DataX + Hive + Spark 离线数仓
- [ ] DolphinScheduler 任务编排

---

## 十一、关键约束

1. **JDK 21 必须用 LTS**，虚拟线程 + 分代 ZGC 是核心收益
2. **Spring Cloud Alibaba 2023.0.1.2** 对应 Spring Boot 3.4.x，版本必须对齐
3. **Nacos 2.4.x** 需要独立部署，不要用嵌入模式
4. **微前端选 wujie 不选 qiankun**——iframe 沙箱隔离更彻底
5. **认证中心独立库**，不要和业务库混用
6. **网关不处理业务逻辑**，只做路由/鉴权/限流
7. **大数据按需接入**，不要一上来就全量，先 Canal + Kafka + Flink 跑通一条链路
