package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.ProfitAnalysisRecordService;
import com.joker.spzx.model.entity.oper.FeeBenchmark;
import com.joker.spzx.model.entity.oper.ProfitAnalysisRecord;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@Tag(description = "利润分析记录", name = "利润分析记录")
@RequestMapping("/admin/mall/profitAnalysis")
public class ProfitAnalysisRecordController {

    @Autowired
    private ProfitAnalysisRecordService profitAnalysisRecordService;

    @PostMapping("/save")
    @Operation(summary = "保存分析记录")
    public Result<String> save(@RequestBody ProfitAnalysisRecord record) {
        profitAnalysisRecordService.saveRecord(record);
        return Result.build(null);
    }

    @GetMapping("/pageList/{productId}/{pageNum}/{pageSize}")
    @Operation(summary = "分页查询分析记录")
    public Result<Page<ProfitAnalysisRecord>> pageList(
            @PathVariable Long productId,
            @PathVariable Integer pageNum,
            @PathVariable Integer pageSize) {
        Page<ProfitAnalysisRecord> page =
                profitAnalysisRecordService.pageByProduct(productId, pageNum, pageSize);
        return Result.build(page);
    }

    @GetMapping("/list/{productId}")
    @Operation(summary = "查询商品全部分析记录")
    public Result<List<ProfitAnalysisRecord>> list(@PathVariable Long productId) {
        List<ProfitAnalysisRecord> list =
                profitAnalysisRecordService.listByProduct(productId);
        return Result.build(list);
    }

    @DeleteMapping("/deleteById/{id}")
    @Operation(summary = "删除分析记录")
    public Result<String> deleteById(@PathVariable Long id) {
        profitAnalysisRecordService.deleteRecord(id);
        return Result.build(null);
    }

    @DeleteMapping("/batchDelete")
    @Operation(summary = "批量删除分析记录")
    public Result<String> batchDelete(@RequestBody List<Long> ids) {
        profitAnalysisRecordService.batchDelete(ids);
        return Result.build(null);
    }

    @DeleteMapping("/clearByProduct/{productId}")
    @Operation(summary = "清空商品分析记录")
    public Result<String> clearByProduct(@PathVariable Long productId) {
        profitAnalysisRecordService.clearByProduct(productId);
        return Result.build(null);
    }

    @GetMapping("/feeBenchmark")
    @Operation(summary = "查询平台×类目费率基准")
    public Result<FeeBenchmark> feeBenchmark(
            @RequestParam Integer platformType,
            @RequestParam(required = false) String category) {
        return Result.build(profitAnalysisRecordService.getFeeBenchmark(platformType, category));
    }
}
