package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.kw.KwExportService;
import com.joker.spzx.manager.service.kw.KwTaskService;
import com.joker.spzx.model.entity.kw.KwSelectTask;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/admin/kw/task")
public class KwTaskController {

    @Autowired
    private KwTaskService kwTaskService;

    @Autowired
    private KwExportService kwExportService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    public record PickDto(List<Long> wordIds, List<Long> titleIds) {
    }

    public record CreateDto(Long productId, Long batchId, String note) {
    }

    @PostMapping("/create")
    public Result<Long> create(@RequestBody CreateDto dto) {
        if (dto.productId() == null || dto.batchId() == null) {
            return Result.build(null, 204, "productId/batchId 必填");
        }
        return Result.build(kwTaskService.create(dto.productId(), dto.batchId(), dto.note()));
    }

    @GetMapping("/list/{pageNum}/{pageSize}")
    public Result<Page<Map<String, Object>>> list(@PathVariable long pageNum,
                                                  @PathVariable long pageSize,
                                                  @RequestParam(required = false) Integer status) {
        LambdaQueryWrapper<KwSelectTask> qw = new LambdaQueryWrapper<KwSelectTask>()
                .orderByDesc(KwSelectTask::getId);
        if (status != null) {
            qw.eq(KwSelectTask::getStatus, status);
        }
        Page<KwSelectTask> page = kwTaskService.getTaskMapper().selectPage(new Page<>(pageNum, pageSize), qw);
        // 一次性 IN 查询补商品编码/标题（原始实体无商品列，前端列空白）
        Map<Long, Map<String, Object>> products = new HashMap<>();
        Set<Long> productIds = page.getRecords().stream()
                .map(KwSelectTask::getProductId).collect(Collectors.toSet());
        if (!productIds.isEmpty()) {
            String in = productIds.stream().map(String::valueOf).collect(Collectors.joining(","));
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(
                    "SELECT id, code, title FROM platform_product WHERE id IN (" + in + ")");
            for (Map<String, Object> r : rows) {
                products.put(((Number) r.get("id")).longValue(), r);
            }
        }
        Page<Map<String, Object>> out = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        List<Map<String, Object>> records = new ArrayList<>();
        for (KwSelectTask t : page.getRecords()) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", t.getId());
            row.put("productId", t.getProductId());
            row.put("batchId", t.getBatchId());
            row.put("analysisId", t.getAnalysisId());
            row.put("note", t.getNote());
            row.put("status", t.getStatus());
            row.put("errorMsg", t.getErrorMsg());
            row.put("textProvider", t.getTextProvider());
            row.put("createTime", t.getCreateTime());
            row.put("finishTime", t.getFinishTime());
            Map<String, Object> p = products.get(t.getProductId());
            row.put("productCode", p == null ? null : p.get("code"));
            row.put("productTitle", p == null ? null : p.get("title"));
            records.add(row);
        }
        out.setRecords(records);
        return Result.build(out);
    }

    @GetMapping("/{id}")
    public Result<Map<String, Object>> detail(@PathVariable Long id) {
        return Result.build(kwTaskService.detail(id));
    }

    @PostMapping("/{id}/retry")
    public Result<Void> retry(@PathVariable Long id) {
        kwTaskService.retry(id);
        return Result.build(null);
    }

    @PostMapping("/{id}/pick")
    public Result<Void> pick(@PathVariable Long id, @RequestBody PickDto dto) {
        if (dto.wordIds() != null && !dto.wordIds().isEmpty()) {
            kwTaskService.pickWords(id, dto.wordIds());
        }
        if (dto.titleIds() != null && !dto.titleIds().isEmpty()) {
            kwTaskService.pickTitles(id, dto.titleIds());
        }
        return Result.build(null);
    }

    @GetMapping("/{id}/export")
    public void export(@PathVariable Long id, jakarta.servlet.http.HttpServletResponse response) throws Exception {
        kwExportService.export(id, response);
    }
}
