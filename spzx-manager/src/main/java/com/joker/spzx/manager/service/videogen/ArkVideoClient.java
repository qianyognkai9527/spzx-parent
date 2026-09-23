package com.joker.spzx.manager.service.videogen;

import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.joker.spzx.manager.service.kw.KwProviderService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 火山方舟 Seedance 视频生成客户端（hutool HttpRequest，风格同 KwAiClient）。
 *
 * <p>契约（external，字段名/路径以 Ark 官方文档为准）：
 * <ul>
 *   <li>提交：{@code POST {base}/contents/generations/tasks} → {@code {id:"cgt-...",status:"queued"}}</li>
 *   <li>查询：{@code GET {base}/contents/generations/tasks/{id}} → status ∈ queued|running|succeeded|failed|expired，成功取 {@code content.video_url}</li>
 * </ul>
 *
 * <p>{@link #buildSubmitBody} 为纯函数（无 IO），便于单测覆盖请求体结构；
 * {@link #submit}/{@link #poll} 走真实 HTTP，由 Task 6 轮询循环消费 {@link ArkStatus#state()}。
 */
@Slf4j
@Service
public class ArkVideoClient {

    /**
     * 轮询状态归一结果。state 取 Ark 语义字符串（queued|running|succeeded|failed），
     * Task 6 直接按 state 字符串 switch，故此处不做数字化归一。
     */
    public record ArkStatus(String state, String videoUrl, String errorMsg) {}

    /**
     * 构造提交请求体（纯函数，不联网）。首帧图通过 content[1].role=first_frame 传入。
     * duration/ratio/generate_audio 为 Ark 视频生成模型参数。
     */
    public String buildSubmitBody(String model, String prompt, String imageDataUrl, int duration, String ratio) {
        JSONObject body = new JSONObject();
        body.set("model", model);
        JSONArray content = new JSONArray();
        content.add(new JSONObject().set("type", "text").set("text", prompt));
        content.add(new JSONObject().set("type", "image_url")
                .set("image_url", new JSONObject().set("url", imageDataUrl))
                .set("role", "first_frame"));
        body.set("content", content);
        body.set("duration", duration);
        body.set("ratio", ratio);
        body.set("generate_audio", false);
        return body.toString();
    }

    /** 提交生成任务，返回 remoteTaskId（Ark 任务 id）。失败抛 RuntimeException。 */
    public String submit(KwProviderService.ProviderDef p, String jsonBody) {
        HttpResponse http = HttpRequest.post(p.baseUrl() + "/contents/generations/tasks")
                .header("Authorization", "Bearer " + p.apiKey())
                .header("Content-Type", "application/json")
                .body(jsonBody).timeout(30_000).execute();
        int status = http.getStatus();
        String resp = http.body();
        JSONObject obj;
        try {
            obj = JSONUtil.parseObj(resp);
        } catch (Exception e) {
            // 非 2xx（HTML/空体/网关错误页）导致 JSON 解析失败：带状态码 + 截断响应体抛出
            throw new RuntimeException("Ark提交失败: HTTP " + status + " " + truncate(resp));
        }
        String id = obj.getStr("id");
        if (id == null || id.isBlank()) {
            JSONObject err = obj.getJSONObject("error");
            throw new RuntimeException(err != null
                    ? "Ark提交失败: " + err.getStr("message", "")
                    : "Ark提交失败: " + truncate(resp));
        }
        log.debug("Ark提交成功 taskId={}", id);
        return id;
    }

    /** 查询任务状态。解析失败/异常向上抛，由 Task 6 轮询循环计入连续失败。 */
    public ArkStatus poll(KwProviderService.ProviderDef p, String taskId) {
        String resp = HttpRequest.get(p.baseUrl() + "/contents/generations/tasks/" + taskId)
                .header("Authorization", "Bearer " + p.apiKey()).timeout(30_000).execute().body();
        JSONObject obj = JSONUtil.parseObj(resp);
        String st = obj.getStr("status", "running");
        return switch (st) {
            case "queued" -> new ArkStatus("queued", null, null);
            case "running" -> new ArkStatus("running", null, null);
            // 视频地址字段路径按 Ark 官方文档取 content.video_url；
            // 若实际响应把地址放 choices/message 变体，此处不做兼容——Task 7 真 Key 联调时按实际响应修正。
            case "succeeded" -> new ArkStatus("succeeded",
                    obj.getJSONObject("content") == null ? null : obj.getJSONObject("content").getStr("video_url"), null);
            default -> new ArkStatus("failed", null,
                    obj.getJSONObject("error") != null ? obj.getJSONObject("error").getStr("message", st) : "生成失败(" + st + ")");
        };
    }

    private static String truncate(String s) {
        if (s == null) return "";
        return s.substring(0, Math.min(200, s.length()));
    }
}
