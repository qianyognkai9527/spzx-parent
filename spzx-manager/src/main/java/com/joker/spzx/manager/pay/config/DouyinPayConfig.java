package com.joker.spzx.manager.pay.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.douyin")
public class DouyinPayConfig {
    private String appId;
    private String merchantId;
    private String privateKey;
    private String notifyUrl;
}
