package com.joker.spzx.manager.pay.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.aggregate")
public class AggregatePayConfig {
    private String channel;
    private String merchantId;
    private String apiKey;
    private String notifyUrl;
}
