package com.joker.spzx.manager.config;

import lombok.extern.slf4j.Slf4j;
import org.kie.api.KieServices;
import org.kie.api.runtime.KieContainer;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Slf4j
@Configuration
@EnableConfigurationProperties(DroolsProperties.class)
@ConditionalOnProperty(prefix = "drools", name = "enabled", havingValue = "true", matchIfMissing = true)
public class DroolsConfig {

    @Bean
    public KieContainer kieContainer(DroolsProperties droolsProperties) {
        KieServices kieServices = KieServices.Factory.get();
        KieContainer kieContainer = kieServices.getKieClasspathContainer();
        log.info("KieContainer 初始化完成，加载规则路径: {}", droolsProperties.getRulesPath());
        return kieContainer;
    }
}
