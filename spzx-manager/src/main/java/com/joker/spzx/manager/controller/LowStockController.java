package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.LowStockService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.LowStockRowVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 低库存规格页：1688 货源规格级低库存（source_sku.stock < 阈值），按货源分组，只显示铺货货源。
 * 阈值白名单 10/20/50；库存数据来自 automation/sourcing 采集链路，映射表
 * taobao_offer_map 由 sku_match_report.json 导入、isv_sku_match.py 每轮刷新。
 * /handle /unhandle 是人工处理留痕（1=下架 2=删除 3=下架SKU），不碰库存与平台。
 */
@RestController
@Tag(name = "低库存规格", description = "1688 货源规格级低库存页 + 人工处理留痕")
@RequestMapping("/admin/lowStock")
public class LowStockController {

    @Autowired
    private LowStockService lowStockService;

    @Operation(summary = "低库存货源分组分页（threshold 白名单 10/20/50；handleStatus all/pending/done；sourceDead no/dead，dead=货源失效视图）")
    @GetMapping("/list")
    public Result<IPage<LowStockRowVo>> list(@RequestParam(required = false) String threshold,
                                             @RequestParam(required = false) String keyword,
                                             @RequestParam(required = false) String handleStatus,
                                             @RequestParam(required = false) String sourceDead,
                                             @RequestParam(required = false, defaultValue = "1") Integer page,
                                             @RequestParam(required = false, defaultValue = "20") Integer size) {
        return Result.build(lowStockService.list(threshold, keyword, handleStatus, sourceDead, page, size));
    }

    @Operation(summary = "人工处理留痕：handleType 1=下架 2=删除 3=下架SKU（重复标记覆盖）")
    @PostMapping("/handle")
    public Result<Void> handle(@RequestParam Long sourceProductId, @RequestParam Integer handleType) {
        lowStockService.mark(sourceProductId, handleType);
        return Result.build(null);
    }

    @Operation(summary = "撤销处理标记")
    @PostMapping("/unhandle")
    public Result<Void> unhandle(@RequestParam Long sourceProductId) {
        lowStockService.clear(sourceProductId);
        return Result.build(null);
    }
}
