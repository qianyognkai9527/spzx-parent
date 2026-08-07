package com.joker.spzx.manager.pay.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.jd")
public class JdPayConfig {
    private String appId;
    private String merchantId;
    private String desKey;
    private String rsaPrivateKey;
    private String notifyUrl;
}
