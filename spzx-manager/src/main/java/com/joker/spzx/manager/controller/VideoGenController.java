package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.videogen.VideoGenTaskService;
import com.joker.spzx.manager.service.videogen.VideoPromptService;
import com.joker.spzx.model.entity.videogen.VideoGenTask;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/videogen")
public class VideoGenController {

    @Autowired
    private VideoPromptService promptService;

    @Autowired
    private VideoGenTaskService taskService;

    @Value("${minio.endpoint:http://127.0.0.1:9000}")
    private String minioEndpoint;

    @Value("${minio.bucket:spzx-manager}")
    private String minioBucket;

    @PostMapping("/prompt")
    public Result<Map<String, Object>> prompt(@RequestBody Map<String, Long> body) {
        Long productId = body == null ? null : body.get("productId");
        if (productId == null) return Result.build(null, 204, "请先选择商品");
        try {
            var r = promptService.generate(productId);
            return Result.build(Map.of("storyboard", r.storyboard(), "prompt", r.prompt()));
        } catch (RuntimeException e) { // 覆盖 IAE 与 hutool JSONException（parsePromptJson 畸形括号输入漏 JSONException）
            return Result.build(null, 204, e.getMessage());
        }
    }

    public record TaskDto(Long productId, String prompt, Integer promptSource, Integer duration, String ratio) {
    }

    @PostMapping("/task")
    public Result<Long> createTask(@RequestBody TaskDto dto) {
        if (dto == null) return Result.build(null, 204, "请求体不能为空");
        try {
            return Result.build(taskService.create(
                    dto.productId(), dto.prompt(), dto.promptSource(), dto.duration(), dto.ratio()));
        } catch (RuntimeException e) { // 校验 IAE / provider 未配置 / 队列满
            return Result.build(null, 204, e.getMessage());
        }
    }

    @GetMapping("/task/list/{pageNum}/{pageSize}")
    public Result<Page<Map<String, Object>>> taskList(@PathVariable long pageNum,
                                                      @PathVariable long pageSize,
                                                      @RequestParam(required = false) Integer status,
                                                      @RequestParam(required = false) Long productId) {
        IPage<VideoGenTask> page = taskService.page(pageNum, pageSize, status, productId);
        // 返回形状与 KwTaskController 一致（Page JSON: records/current/size/total），前端复用分页约定
        Page<Map<String, Object>> out = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        List<Map<String, Object>> rows = new ArrayList<>(page.getRecords().size());
        for (VideoGenTask t : page.getRecords()) {
            rows.add(taskRow(t));
        }
        out.setRecords(rows);
        return Result.build(out);
    }

    @GetMapping("/task/{id}")
    public Result<Map<String, Object>> taskDetail(@PathVariable Long id) {
        VideoGenTask t = taskService.getById(id);
        if (t == null) return Result.build(null, 204, "任务不存在");
        return Result.build(taskRow(t));
    }

    @PostMapping("/task/{id}/retry")
    public Result<Void> taskRetry(@PathVariable Long id) {
        try {
            taskService.retry(id);
            return Result.build(null);
        } catch (RuntimeException e) { // 仅失败可重试 / 队列满
            return Result.build(null, 204, e.getMessage());
        }
    }

    @DeleteMapping("/task/{id}")
    public Result<Void> taskDelete(@PathVariable Long id) {
        taskService.delete(id);
        return Result.build(null);
    }

    /** 任务实体 → 前端行 VO：拼 videoUrl（objectKey → MinIO 完整 URL，浏览器/`<video>` 直连，无 302 接口） */
    private Map<String, Object> taskRow(VideoGenTask t) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", t.getId());
        row.put("productId", t.getProductId());
        row.put("prompt", t.getPrompt());
        row.put("promptSource", t.getPromptSource());
        row.put("model", t.getModel());
        row.put("duration", t.getDuration());
        row.put("ratio", t.getRatio());
        row.put("status", t.getStatus());
        row.put("remoteTaskId", t.getRemoteTaskId());
        row.put("errorMsg", t.getErrorMsg());
        row.put("videoUrl", t.getObjectKey() == null || t.getObjectKey().isBlank()
                ? null : minioEndpoint + "/" + minioBucket + "/" + t.getObjectKey());
        row.put("createTime", t.getCreateTime());
        row.put("finishTime", t.getFinishTime());
        return row;
    }
}
