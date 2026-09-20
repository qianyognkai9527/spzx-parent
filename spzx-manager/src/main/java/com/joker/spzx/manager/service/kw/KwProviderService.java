package com.joker.spzx.manager.service.kw;

import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.mapper.KwProviderMapper;
import com.joker.spzx.model.entity.kw.KwProvider;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwProviderService {

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
            String visionModel, String textModel,
            Integer maxTokens, Map<String, Object> extraBody) {

        public String modelFor(String kind) {
            return "vision".equals(kind) ? visionModel : textModel;
        }
    }

    /** 启动播种：表空且 yml kw.providers 非空 → 按 yml 现值插入；表不存在仅 warn 跳过不阻塞启动 */
    @PostConstruct
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
                .eq(KwProvider::getName, name).last("limit 1"));
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
        String model = "vision".equals(kind) ? row.getVisionModel() : row.getTextModel();
        if (model == null || model.isBlank()) {
            throw new RuntimeException("provider " + name + " 未配置 " + kind + " 模型");
        }
        return toDef(row);
    }

    public List<KwProvider> listAll() {
        return kwProviderMapper.selectList(new LambdaQueryWrapper<KwProvider>()
                .orderByAsc(KwProvider::getId));
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
                row.getVisionModel(), row.getTextModel(), row.getMaxTokens(), extra);
    }
}
