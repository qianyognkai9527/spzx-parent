package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.kw.KwTaskService;
import com.joker.spzx.model.entity.kw.KwSelectTask;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/kw/task")
public class KwTaskController {

    @Autowired
    private KwTaskService kwTaskService;

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
    public Result<IPage<KwSelectTask>> list(@PathVariable long pageNum,
                                            @PathVariable long pageSize,
                                            @RequestParam(required = false) Integer status) {
        LambdaQueryWrapper<KwSelectTask> qw = new LambdaQueryWrapper<KwSelectTask>()
                .orderByDesc(KwSelectTask::getId);
        if (status != null) {
            qw.eq(KwSelectTask::getStatus, status);
        }
        return Result.build(kwTaskService.getTaskMapper().selectPage(new Page<>(pageNum, pageSize), qw));
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
}
