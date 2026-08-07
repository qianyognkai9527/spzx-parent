package com.joker.spzx.manager.pay.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.stripe")
public class StripeConfig {
    private String apiKey;
    private String webhookSecret;
    private String notifyUrl;
}
