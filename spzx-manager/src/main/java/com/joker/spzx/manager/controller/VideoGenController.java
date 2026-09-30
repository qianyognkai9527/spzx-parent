package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.FileService;
import com.joker.spzx.manager.service.videogen.VideoGenTaskService;
import com.joker.spzx.manager.service.videogen.VideoPromptService;
import com.joker.spzx.model.entity.videogen.VideoGenTask;
import com.joker.spzx.model.vo.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
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

@Slf4j
@RestController
@RequestMapping("/admin/videogen")
public class VideoGenController {

    @Autowired
    private VideoPromptService promptService;

    @Autowired
    private VideoGenTaskService taskService;

    @Autowired
    private FileService fileService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

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

    /** 计费预览：当前视频模型 5秒档单价 + 按预计时长折算的本单费用 + 日预算执行情况（不落库） */
    @GetMapping("/cost-estimate")
    public Result<Map<String, Object>> costEstimate(@RequestParam(required = false, defaultValue = "5") Integer duration) {
        try {
            return Result.build(taskService.costEstimate(duration));
        } catch (RuntimeException e) { // provider 未配置等
            return Result.build(null, 204, e.getMessage());
        }
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

    public record BatchDto(List<Long> productIds, Integer duration, String ratio) {
    }

    /** 批量生成：提示词由工作线程逐个生成；返回 {created, skipped, estCostTotal} */
    @PostMapping("/task/batch")
    public Result<Map<String, Object>> createBatch(@RequestBody BatchDto dto) {
        if (dto == null) return Result.build(null, 204, "请求体不能为空");
        try {
            return Result.build(taskService.createBatch(dto.productIds(), dto.duration(), dto.ratio()));
        } catch (RuntimeException e) { // 校验 IAE / provider 未配置 / 超预算
            return Result.build(null, 204, e.getMessage());
        }
    }

    @GetMapping("/task/list/{pageNum}/{pageSize}")    public Result<Page<Map<String, Object>>> taskList(@PathVariable long pageNum,
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

    /** 成片挂回商品媒体（file_type=2，remark 带 AI 生成标识）；返回媒体行 id */
    @PostMapping("/task/{id}/attach")
    public Result<Long> attachTask(@PathVariable Long id) {
        try {
            return Result.build(taskService.attachToProductMedia(id));
        } catch (RuntimeException e) { // 未生成成功 / 商品无媒体
            return Result.build(null, 204, e.getMessage());
        }
    }

    @DeleteMapping("/task/{id}")
    public Result<Void> taskDelete(@PathVariable Long id) {
        taskService.delete(id);
        return Result.build(null);
    }

    /** 任务实体 → 前端行 VO：拼 videoUrl（预览直链）与 downloadUrl（预签名 attachment 直链，跨域也能另存为） */
    private Map<String, Object> taskRow(VideoGenTask t) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", t.getId());
        row.put("productId", t.getProductId());
        row.put("prompt", t.getPrompt());
        row.put("promptSource", t.getPromptSource());
        row.put("model", t.getModel());
        row.put("duration", t.getDuration());
        row.put("ratio", t.getRatio());
        row.put("estCost", t.getEstCost());
        row.put("status", t.getStatus());
        row.put("remoteTaskId", t.getRemoteTaskId());
        row.put("errorMsg", t.getErrorMsg());
        boolean hasKey = t.getObjectKey() != null && !t.getObjectKey().isBlank();
        row.put("videoUrl", hasKey ? taskService.objectUrl(t.getObjectKey()) : null);
        row.put("downloadUrl", hasKey
                ? fileService.presignedDownloadUrl(t.getObjectKey(), downloadFilename(t)) : null);
        row.put("createTime", t.getCreateTime());
        row.put("finishTime", t.getFinishTime());
        return row;
    }

    /** 下载文件名：商品编码存在则 code_id.mp4，否则 videogen_id.mp4；仅保留 HTTP 头安全字符 */
    private String downloadFilename(VideoGenTask t) {
        String code = null;
        try {
            List<String> codes = jdbcTemplate.queryForList(
                    "SELECT code FROM platform_product WHERE id=?", String.class, t.getProductId());
            if (!codes.isEmpty() && codes.get(0) != null) {
                code = codes.get(0).replaceAll("[^A-Za-z0-9._-]", "");
            }
        } catch (Exception e) { // 编码查询失败退回默认命名，不阻塞列表
            log.warn("videogen 下载名查询商品编码失败 product_id={}: {}", t.getProductId(), e.getMessage());
        }
        return (code == null || code.isBlank() ? "videogen_" + t.getId() : code + "_" + t.getId()) + ".mp4";
    }
}
