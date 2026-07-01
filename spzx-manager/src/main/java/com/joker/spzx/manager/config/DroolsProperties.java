package com.joker.spzx.manager.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "drools")
public class DroolsProperties {

    /**
     * 是否启用 Drools
     */
    private boolean enabled = true;

    /**
     * classpath 下规则文件目录，例如 rules/
     */
    private String rulesPath = "rules/";
}
