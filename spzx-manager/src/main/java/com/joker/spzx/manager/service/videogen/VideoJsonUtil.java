package com.joker.spzx.manager.service.videogen;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import java.util.List;
import java.util.Map;

/**
 * LLM 返回内容中 JSON 的提取与 prompt 解析纯函数（videogen 专用，无 Spring 依赖）。
 */
public final class VideoJsonUtil {

    /** 解析结果：分镜列表 + 主体描述 prompt。 */
    public record VideoPromptResult(List<Map<String, Object>> storyboard, String prompt) {}

    private VideoJsonUtil() {}

    /** 返回首个 '{' 到末个 '}' 的子串；无花括号或 content 为 null 时返回 null。 */
    public static String extractJsonObject(String content) {
        if (content == null) return null;
        int s = content.indexOf('{');
        int e = content.lastIndexOf('}');
        return s >= 0 && e > s ? content.substring(s, e + 1) : null;
    }

    /** 解析 AI 返回的 {storyboard:[...], prompt:"..."}；解析失败抛 IllegalArgumentException。 */
    public static VideoPromptResult parsePromptJson(String llmContent) {
        String json = extractJsonObject(llmContent);
        if (json == null) throw new IllegalArgumentException("AI返回非JSON，请重试");
        JSONObject obj = JSONUtil.parseObj(json);
        String prompt = obj.getStr("prompt", "").trim();
        if (prompt.isEmpty()) throw new IllegalArgumentException("AI返回缺少prompt字段");
        List<Map<String, Object>> board = obj.getJSONArray("storyboard") == null
                ? List.of() : obj.getJSONArray("storyboard").stream()
                .map(o -> o instanceof JSONObject jo
                        ? (Map<String, Object>) jo
                        : (Map<String, Object>) JSONUtil.parseObj(o))
                .toList();
        return new VideoPromptResult(board, prompt.length() > 2000 ? prompt.substring(0, 2000) : prompt);
    }
}
