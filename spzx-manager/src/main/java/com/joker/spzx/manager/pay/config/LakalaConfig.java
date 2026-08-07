package com.joker.spzx.manager.pay.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.lakala")
public class LakalaConfig {
    private String merchantId;
    private String serialNo;
    private String privateKey;
    private String publicKey;
    private String notifyUrl;
}
