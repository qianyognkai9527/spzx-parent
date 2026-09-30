package com.joker.spzx.manager.service.kw;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.config.KwProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwAiClient {

    @Autowired
    private KwProperties props;

    @Autowired
    private KwConfigService kwConfigService;

    @Autowired
    private KwProviderService kwProviderService;

    /** 文本补全（选词/标题） */
    public String text(String providerName, String prompt) {
        JSONArray messages = new JSONArray();
        JSONObject msg = new JSONObject();
        msg.set("role", "user");
        msg.set("content", prompt);
        messages.add(msg);
        return call(providerName, "text", messages);
    }

    /** 视觉补全（识品）：contentParts 为 OpenAI 多模态 content 数组 */
    public String vision(String providerName, List<Map<String, Object>> contentParts) {
        JSONArray messages = new JSONArray();
        JSONObject msg = new JSONObject();
        msg.set("role", "user");
        msg.set("content", contentParts);
        messages.add(msg);
        return call(providerName, "vision", messages);
    }

    private String call(String providerName, String kind, JSONArray messages) {
        List<String> tried = new ArrayList<>();
        tried.add(providerName);
        RuntimeException last = null;
        try {
            return callOnce(providerName, kind, messages);
        } catch (RuntimeException e) {
            last = e;
        }
        // 主用引擎两次都失败 → 依次尝试其它配了该 kind 模型的启用引擎，避免单引擎故障卡死整批任务
        for (KwProviderService.ProviderDef alt : kwProviderService.alternatives(kind, tried)) {
            tried.add(alt.name());
            log.warn("kw降级到备用引擎: {} -> {} (kind={})", providerName, alt.name(), kind);
            try {
                return callOnce(alt.name(), kind, messages);
            } catch (RuntimeException e) {
                last = e;
            }
        }
        throw last;
    }

    /** 单引擎最多两次尝试，仍失败则抛出最后一次异常 */
    private String callOnce(String providerName, String kind, JSONArray messages) {
        KwProviderService.ProviderDef p = kwProviderService.requireActive(providerName, kind);
        String model = p.modelFor(kind);
        RuntimeException last = null;
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                JSONObject body = new JSONObject();
                body.set("model", model);
                body.set("messages", messages);
                body.set("temperature", 0.3);
                // reasoning 模型（如 glm-5.3-flash）会先产出思考内容，max_tokens 必须给足；默认 4096，可在 provider 配置 max-tokens 覆盖
                body.set("max_tokens", p.maxTokens() != null ? p.maxTokens() : 4096);
                // provider 可注入额外请求参数（如 thinking.type=disabled 关闭深度思考，避免推理耗尽 max_tokens）
                if (p.extraBody() != null) {
                    p.extraBody().forEach(body::set);
                }
                String resp = HttpRequest.post(p.baseUrl() + "/chat/completions")
                        .header("Authorization", "Bearer " + p.apiKey())
                        .header("Content-Type", "application/json")
                        .body(body.toString())
                        .timeout(props.getTimeoutMs())
                        .execute()
                        .body();
                JSONObject respJson = JSONUtil.parseObj(resp);
                if (respJson.containsKey("error")) {
                    throw new RuntimeException("AI错误: "
                            + respJson.getJSONObject("error").getStr("message", ""));
                }
                JSONArray choices = respJson.getJSONArray("choices");
                if (choices == null || choices.isEmpty()) {
                    throw new RuntimeException("AI返回空choices");
                }
                String content = choices.getJSONObject(0).getJSONObject("message").getStr("content", "");
                if (content == null || content.isBlank()) {
                    throw new RuntimeException("AI返回空content(可能max_tokens被reasoning耗尽)");
                }
                return stripFence(content.trim());
            } catch (RuntimeException e) {
                last = e;
                log.warn("kw AI调用失败(attempt {}/2, provider={}, model={}): {}",
                        attempt, providerName, model, e.getMessage());
            }
        }
        throw last;
    }

    private String stripFence(String c) {
        return c.replaceAll("^```(json)?", "").replaceAll("```$", "").trim();
    }
}
