package com.joker.spzx.manager.pay.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.unionpay")
public class UnionPayConfig {
    private String merchantId;
    private String certPath;
    private String certPassword;
    private String frontUrl;
    private String backUrl;
    private boolean sandbox;
}
