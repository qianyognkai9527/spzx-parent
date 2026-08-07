package com.joker.spzx.manager.pay.config;

import com.github.binarywang.wxpay.service.WxPayService;
import com.github.binarywang.wxpay.service.impl.WxPayServiceImpl;
import lombok.Data;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.wechat")
public class WxPayConfig {

    private String appId;
    private String mchId;
    private String mchKey;
    private String keyPath;
    private String notifyUrl;
    private String refundNotifyUrl;
    private String miniAppId;

    @Bean
    @ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
    public WxPayService wxPayService() {
        com.github.binarywang.wxpay.config.WxPayConfig config = new com.github.binarywang.wxpay.config.WxPayConfig();
        config.setAppId(appId);
        config.setMchId(mchId);
        config.setMchKey(mchKey);
        config.setKeyPath(keyPath);
        config.setNotifyUrl(notifyUrl);
        config.setTradeType("NATIVE");
        WxPayService service = new WxPayServiceImpl();
        service.setConfig(config);
        return service;
    }
}
