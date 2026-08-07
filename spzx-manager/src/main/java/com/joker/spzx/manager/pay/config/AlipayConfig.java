package com.joker.spzx.manager.pay.config;

import com.alipay.api.AlipayClient;
import com.alipay.api.DefaultAlipayClient;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.alipay")
public class AlipayConfig {

    private String appId;
    private String privateKey;
    private String alipayPublicKey;
    private String gatewayUrl;
    private String notifyUrl;
    private String refundNotifyUrl;
    private String format = "json";
    private String charset = "UTF-8";
    private String signType = "RSA2";

    @Bean
    public AlipayClient alipayClient() {
        return new DefaultAlipayClient(
                gatewayUrl, appId, privateKey, format, charset, alipayPublicKey, signType);
    }
}
