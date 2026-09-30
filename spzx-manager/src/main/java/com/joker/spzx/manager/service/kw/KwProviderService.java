package com.joker.spzx.manager.service.kw;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.common.util.SqlConstants;
import com.joker.spzx.manager.mapper.KwProviderMapper;
import com.joker.spzx.model.entity.kw.KwProvider;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwProviderService implements ApplicationRunner {

    @Autowired
    private KwProviderMapper kwProviderMapper;

    @Autowired
    private KwProperties props;

    /**
     * 运行时 provider 定义。KwAiClient 每次调用现读 DB，无缓存——
     * 本地 MySQL 单查 ~1ms 对比 LLM 秒级调用可忽略，页面改动即时生效。
     */
    public record ProviderDef(
            String name, String baseUrl, String apiKey,
            String visionModel, String textModel, String videoModel,
            java.math.BigDecimal videoPrice,
            Integer maxTokens, Map<String, Object> extraBody) {

        public String modelFor(String kind) {
            return modelOf(visionModel, textModel, videoModel, kind);
        }
    }

    /** kind → 模型列的映射只此一处；新增 kind（如 image）改这里，别再抄 switch */
    public static String modelOf(String visionModel, String textModel, String videoModel, String kind) {
        return switch (kind) {
            case "vision" -> visionModel;
            case "video" -> videoModel;
            default -> textModel;
        };
    }

    public static String modelOf(KwProvider row, String kind) {
        return modelOf(row.getVisionModel(), row.getTextModel(), row.getVideoModel(), kind);
    }

    /** 启动播种：SpringApplication.callRunners 强制实例化 runner，不受 lazy-initialization 影响 */
    @Override
    public void run(ApplicationArguments args) {
        seed();
    }

    /** 表空且 yml kw.providers 非空 → 按 yml 现值插入；表不存在仅 warn 跳过不阻塞启动 */
    public void seed() {
        try {
            Long count = kwProviderMapper.selectCount(null);
            if (count != null && count > 0) {
                return;
            }
            if (props.getProviders().isEmpty()) {
                return;
            }
            for (Map.Entry<String, KwProperties.Provider> e : props.getProviders().entrySet()) {
                KwProperties.Provider p = e.getValue();
                KwProvider row = new KwProvider();
                row.setName(e.getKey());
                row.setBaseUrl(p.getBaseUrl());
                row.setApiKey(p.getApiKey() == null ? "" : p.getApiKey());
                row.setVisionModel(p.getVisionModel());
                row.setTextModel(p.getTextModel());
                row.setMaxTokens(p.getMaxTokens());
                row.setExtraBody(p.getExtraBody() == null || p.getExtraBody().isEmpty()
                        ? null : JSONUtil.toJsonStr(p.getExtraBody()));
                row.setStatus(1);
                row.setRemark("从yml自动播种");
                kwProviderMapper.insert(row);
            }
            log.info("已从 yml 播种 {} 个 provider 到 kw_provider 表", props.getProviders().size());
        } catch (Exception e) {
            log.warn("kw_provider 播种跳过（表可能未创建）: {}", e.getMessage());
        }
    }

    public KwProvider getEntity(String name) {
        return kwProviderMapper.selectOne(new LambdaQueryWrapper<KwProvider>()
                .eq(KwProvider::getName, name).last(SqlConstants.LIMIT_1));
    }

    public ProviderDef get(String name) {
        KwProvider row = getEntity(name);
        return row == null ? null : toDef(row);
    }

    /** 校验存在 + 启用 + 有 key + kind 对应模型已配，不满足抛 RuntimeException（沿用 KwAiClient 报错语义） */
    public ProviderDef requireActive(String name, String kind) {
        KwProvider row = getEntity(name);
        if (row == null || row.getBaseUrl() == null || row.getBaseUrl().isBlank()) {
            throw new RuntimeException("AI provider 未配置: " + name);
        }
        if (row.getStatus() == null || row.getStatus() != 1) {
            throw new RuntimeException("AI provider 已停用: " + name);
        }
        if (row.getApiKey() == null || row.getApiKey().isBlank()) {
            throw new RuntimeException("AI provider 未配置 key: " + name);
        }
        String model = modelOf(row, kind);
        if (model == null || model.isBlank()) {
            throw new RuntimeException("provider " + name + " 未配置 " + kind + " 模型");
        }
        return toDef(row);
    }

    public List<KwProvider> listAll() {
        return kwProviderMapper.selectList(new LambdaQueryWrapper<KwProvider>()
                .orderByAsc(KwProvider::getId));
    }

    /** 备用引擎：启用中、配了该 kind 模型、有 key，排除主用与 alreadyTried，按 id 升序 */
    public List<ProviderDef> alternatives(String kind, List<String> alreadyTried) {
        List<ProviderDef> out = new java.util.ArrayList<>();
        for (KwProvider row : listAll()) {
            if (alreadyTried != null && alreadyTried.contains(row.getName())) continue;
            if (row.getStatus() == null || row.getStatus() != 1) continue;
            if (row.getApiKey() == null || row.getApiKey().isBlank()) continue;
            if (row.getBaseUrl() == null || row.getBaseUrl().isBlank()) continue;
            String model = modelOf(row, kind);
            if (model == null || model.isBlank()) continue;
            out.add(toDef(row));
        }
        return out;
    }

    public ProviderDef toDef(KwProvider row) {
        Map<String, Object> extra = null;
        if (row.getExtraBody() != null && !row.getExtraBody().isBlank()) {
            try {
                extra = JSONUtil.parseObj(row.getExtraBody());
            } catch (Exception e) {
                log.warn("provider {} extra_body 非法JSON，忽略: {}", row.getName(), e.getMessage());
            }
        }
        return new ProviderDef(row.getName(), row.getBaseUrl(), row.getApiKey(),
                row.getVisionModel(), row.getTextModel(), row.getVideoModel(), row.getVideoPrice(),
                row.getMaxTokens(), extra);
    }
}
