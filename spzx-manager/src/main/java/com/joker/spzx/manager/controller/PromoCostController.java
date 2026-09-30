package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.promo.PromoCostService;
import com.joker.spzx.model.entity.promo.PromoImportMap;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;

/**
 * 淘宝付费推广日报导入：先预览（把没映射上的列报出来）、再落库；列名映射是可编辑的数据。
 */
@RestController
@Tag(name = "推广日报导入", description = "关键词推广/人群推广日报的列名映射与导入")
@RequestMapping("/admin/promo")
public class PromoCostController {

    @Autowired
    private PromoCostService promoCostService;

    @Operation(summary = "列名映射列表")
    @GetMapping("/mapping/list")
    public Result<List<PromoImportMap>> mappings(@RequestParam(required = false) String reportLevel) {
        return Result.build(promoCostService.listMappings(reportLevel));
    }

    @PostMapping("/mapping")
    public Result<Void> createMapping(@RequestBody PromoImportMap map) {
        String err = promoCostService.validateMapping(map);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = promoCostService.mappingConflict(map);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        promoCostService.saveMapping(map);
        return Result.build(null);
    }

    @PutMapping("/mapping/{id}")
    public Result<Void> updateMapping(@PathVariable Long id, @RequestBody PromoImportMap map) {
        if (promoCostService.getMapping(id) == null) {
            return Result.build(null, 204, "映射不存在");
        }
        map.setId(id);
        String err = promoCostService.validateMapping(map);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = promoCostService.mappingConflict(map);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        promoCostService.updateMapping(map);
        return Result.build(null);
    }

    @DeleteMapping("/mapping/{id}")
    public Result<Void> deleteMapping(@PathVariable Long id) {
        promoCostService.deleteMapping(id);
        return Result.build(null);
    }

    /**
     * 导入一份报表。preview 与 commit 走同一段解析，只是 dryRun 不同：
     * 第一次拿到真实导出文件时先 preview，看 unmapped 里还有哪些列没对上。
     */
    @Operation(summary = "预览导入（不写库）")
    @PostMapping("/import/preview")
    public Result<PromoCostService.ImportResult> preview(@RequestParam("file") MultipartFile file,
                                                         @RequestParam(defaultValue = "campaign") String reportLevel,
                                                         @RequestParam(defaultValue = "keyword") String planType,
                                                         @RequestParam(required = false) Long shopId,
                                                         @RequestParam(required = false) String reportSource) {
        return doImport(file, reportLevel, planType, shopId, reportSource, true);
    }

    @Operation(summary = "正式导入（按自然键 upsert，可重复执行）")
    @PostMapping("/import/commit")
    public Result<PromoCostService.ImportResult> commit(@RequestParam("file") MultipartFile file,
                                                        @RequestParam(defaultValue = "campaign") String reportLevel,
                                                        @RequestParam(defaultValue = "keyword") String planType,
                                                        @RequestParam(required = false) Long shopId,
                                                        @RequestParam(required = false) String reportSource) {
        return doImport(file, reportLevel, planType, shopId, reportSource, false);
    }

    @Operation(summary = "按批次号回滚一次导入")
    @DeleteMapping("/import/batch/{batch}")
    public Result<Integer> rollback(@PathVariable String batch) {
        return Result.build(promoCostService.deleteBatch(batch));
    }

    private Result<PromoCostService.ImportResult> doImport(MultipartFile file, String reportLevel, String planType,
                                                           Long shopId, String reportSource, boolean dryRun) {
        if (file == null || file.isEmpty()) {
            return Result.build(null, 204, "请选择要导入的报表 CSV 文件");
        }
        String name = file.getOriginalFilename();
        if (name != null && !name.toLowerCase().endsWith(".csv")) {
            return Result.build(null, 204, "只支持 CSV 文件");
        }
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException e) {
            return Result.build(null, 204, "读取上传文件失败：" + e.getMessage());
        }
        String source = reportSource == null || reportSource.isBlank() ? (name == null ? "" : name) : reportSource.trim();
        return Result.build(promoCostService.importCsv(bytes, reportLevel, planType, shopId, source, dryRun));
    }
}
