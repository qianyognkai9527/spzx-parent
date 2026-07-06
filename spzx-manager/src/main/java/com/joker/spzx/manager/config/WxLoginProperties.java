package com.joker.spzx.manager.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "wx.login")
public class WxLoginProperties {

    private String appId;
    private String appSecret;
    private String redirectUri;
    private String authUrl = "https://open.weixin.qq.com/connect/qrconnect";
    private String accessTokenUrl = "https://api.weixin.qq.com/sns/oauth2/access_token";
    private String userInfoUrl = "https://api.weixin.qq.com/sns/userinfo";
    private Integer qrTtlSeconds = 120;
    private Long pollIntervalMs = 1500L;
    private Boolean mockMode = true;
    private String mockBaseUrl = "http://localhost:80";
}
