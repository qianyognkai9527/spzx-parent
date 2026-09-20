package com.joker.spzx.manager.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

@Data
@Component
@ConfigurationProperties(prefix = "kw")
public class KwProperties {

    /** providers 仅用于首次播种 kw_provider 表（表空时）；运行时配置读 DB，改 yml 此节不再生效 */
    private Map<String, Provider> providers = new LinkedHashMap<>();
    private int topN = 2000;
    private int batchSize = 100;
    private int minPopularity = 60;
    private int imageCount = 5;
    private int timeoutMs = 180000;
    private Weights weights = new Weights();

    @Data
    public static class Provider {
        private String baseUrl;
        private String apiKey;
        private String visionModel;
        private String textModel;
        private Integer maxTokens;
        private Map<String, Object> extraBody;
    }

    @Data
    public static class Weights {
        private double popularity = 0.30;
        private double clickRate = 0.25;
        private double convRate = 0.25;
        private double buyer = 0.20;
    }
}
