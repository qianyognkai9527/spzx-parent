package com.joker.spzx.manager.service.kw;

import cn.hutool.http.HttpRequest;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.config.KwProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwAiClient {

    @Autowired
    private KwProperties props;

    @Autowired
    private KwConfigService kwConfigService;

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
        KwProperties.Provider p = props.getProviders().get(providerName);
        if (p == null || p.getBaseUrl() == null || p.getApiKey() == null || p.getApiKey().isBlank()) {
            throw new RuntimeException("AI provider 未配置: " + providerName);
        }
        String model = "vision".equals(kind) ? p.getVisionModel() : p.getTextModel();
        if (model == null || model.isBlank()) {
            throw new RuntimeException("provider " + providerName + " 未配置 " + kind + " 模型");
        }
        RuntimeException last = null;
        for (int attempt = 1; attempt <= 2; attempt++) {
            try {
                JSONObject body = new JSONObject();
                body.set("model", model);
                body.set("messages", messages);
                body.set("temperature", 0.3);
                // reasoning 模型（如 glm-5.3-flash）会先产出思考内容，max_tokens 必须给足；默认 4096，可在 provider 配置 max-tokens 覆盖
                body.set("max_tokens", p.getMaxTokens() != null ? p.getMaxTokens() : 4096);
                // provider 可注入额外请求参数（如 thinking.type=disabled 关闭深度思考，避免推理耗尽 max_tokens）
                if (p.getExtraBody() != null) {
                    p.getExtraBody().forEach(body::set);
                }
                String resp = HttpRequest.post(p.getBaseUrl() + "/chat/completions")
                        .header("Authorization", "Bearer " + p.getApiKey())
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
