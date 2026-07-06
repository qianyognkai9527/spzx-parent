-- ============================================================
-- 微信扫码登录功能 - 建表脚本
-- 数据库: db_spzx
-- ============================================================

-- 1. 微信用户绑定表
CREATE TABLE IF NOT EXISTS `sys_wechat_user` (
    `id`              BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT                COMMENT '主键ID',
    `user_id`         BIGINT UNSIGNED  NOT NULL                               COMMENT '绑定的本地系统用户ID(sys_user.id)',
    `openid`          CHAR(28)         NOT NULL                               COMMENT '微信OpenID(当前AppID下唯一)',
    `unionid`         CHAR(28)         DEFAULT NULL                           COMMENT '微信UnionID(跨应用唯一,同一开放平台下)',
    `appid`           VARCHAR(32)      NOT NULL                               COMMENT '微信应用AppID(支持多应用)',
    `nickname`        VARCHAR(64)      DEFAULT NULL                           COMMENT '微信昵称(授权时获取)',
    `avatar_url`      VARCHAR(512)     DEFAULT NULL                           COMMENT '微信头像URL',
    `sex`             TINYINT UNSIGNED NOT NULL DEFAULT 0                     COMMENT '性别(0未知 1男 2女)',
    `country`         VARCHAR(32)      DEFAULT NULL                           COMMENT '国家',
    `province`        VARCHAR(32)      DEFAULT NULL                           COMMENT '省份',
    `city`            VARCHAR(32)      DEFAULT NULL                           COMMENT '城市',
    `bind_status`     TINYINT UNSIGNED NOT NULL DEFAULT 1                     COMMENT '绑定状态(1正常 0已解绑)',
    `last_login_time` DATETIME         DEFAULT NULL                           COMMENT '最后微信扫码登录时间',
    `last_login_ip`   VARCHAR(45)      DEFAULT NULL                           COMMENT '最后登录IP',
    `create_time`     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP     COMMENT '创建时间',
    `update_time`     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `is_deleted`      TINYINT UNSIGNED NOT NULL DEFAULT 0                     COMMENT '逻辑删除(0未删 1已删)',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_appid_openid` (`appid`, `openid`),
    UNIQUE KEY `uk_unionid_appid` (`unionid`, `appid`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_bind_status` (`bind_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='微信用户绑定表';

-- 2. 扫码登录票据表
CREATE TABLE IF NOT EXISTS `sys_qr_login_ticket` (
    `id`          BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT                COMMENT '主键ID',
    `ticket`      CHAR(32)         NOT NULL                               COMMENT '票据(UUID去横线,前端轮询凭证)',
    `state`       CHAR(32)         NOT NULL                               COMMENT 'OAuth2 state(防CSRF,回调校验)',
    `status`      TINYINT UNSIGNED NOT NULL DEFAULT 0                     COMMENT '状态(0待扫描 1已扫描 2已确认 3已过期 4已取消 5需绑定)',
    `user_id`     BIGINT UNSIGNED  DEFAULT NULL                           COMMENT '登录用户ID(确认后回填)',
    `openid`      CHAR(28)         DEFAULT NULL                           COMMENT '扫码者OpenID',
    `client_ip`   VARCHAR(45)      DEFAULT NULL                           COMMENT '发起扫码的PC端IP',
    `expire_time` DATETIME         NOT NULL                               COMMENT '票据过期时间(创建+2min)',
    `create_time` DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP     COMMENT '创建时间',
    `update_time` DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_ticket` (`ticket`),
    KEY `idx_state` (`state`),
    KEY `idx_status_expire` (`status`, `expire_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='扫码登录票据表';

-- 3. 登录日志表
CREATE TABLE IF NOT EXISTS `sys_login_log` (
    `id`           BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT                COMMENT '主键ID',
    `user_id`      BIGINT UNSIGNED  DEFAULT NULL                           COMMENT '用户ID(登录失败可为空)',
    `username`     VARCHAR(64)      DEFAULT NULL                           COMMENT '用户名或微信昵称',
    `login_type`   TINYINT UNSIGNED NOT NULL                               COMMENT '登录方式(1密码 2微信扫码)',
    `login_status` TINYINT UNSIGNED NOT NULL                               COMMENT '登录状态(1成功 0失败)',
    `openid`       CHAR(28)         DEFAULT NULL                           COMMENT '微信OpenID(微信登录时)',
    `ip_address`   VARCHAR(45)      DEFAULT NULL                           COMMENT '客户端IP(支持IPv6)',
    `user_agent`   VARCHAR(256)     DEFAULT NULL                           COMMENT 'User-Agent(截断)',
    `location`     VARCHAR(128)     DEFAULT NULL                           COMMENT '登录地点(IP解析)',
    `fail_reason`  VARCHAR(128)     DEFAULT NULL                           COMMENT '失败原因(失败时)',
    `create_time`  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP     COMMENT '登录时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_create_time` (`create_time`),
    KEY `idx_login_type_status` (`login_type`, `login_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录日志表';
