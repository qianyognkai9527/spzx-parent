package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.ItemOpsService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.ItemOpsVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 商品运营台：在售商品的经营指标与成本毛利，只读。
 */
@RestController
@Tag(name = "商品运营台", description = "平台商品 × 近7日效果 × 货源成本")
@RequestMapping("/admin/mall/itemOps")
public class ItemOpsController {

    @Autowired
    private ItemOpsService itemOpsService;

    @Operation(summary = "分页查询，facet 可选 all/noSale/negativeMargin/lowStock/noEffect/noSource/unpriced")
    @GetMapping("/page/{pageNum}/{pageSize}")
    public Result<IPage<ItemOpsVo>> page(@PathVariable long pageNum,
                                         @PathVariable long pageSize,
                                         @RequestParam(required = false) Integer platformType,
                                         @RequestParam(required = false) Long shopId,
                                         @RequestParam(required = false) String keyword,
                                         @RequestParam(required = false, defaultValue = "all") String facet,
                                         @RequestParam(required = false) Integer stockThreshold,
                                         @RequestParam(required = false) Integer uvFrom) {
        return Result.build(itemOpsService.page(
                pageNum, pageSize, platformType, shopId, keyword, facet, stockThreshold, uvFrom));
    }

    @Operation(summary = "各筛选项的商品数（与分页同一套筛选口径）")
    @GetMapping("/facetCounts")
    public Result<java.util.Map<String, Object>> facetCounts(@RequestParam(required = false) Integer platformType,
                                                            @RequestParam(required = false) Long shopId,
                                                            @RequestParam(required = false) String keyword,
                                                            @RequestParam(required = false) Integer stockThreshold,
                                                            @RequestParam(required = false) Integer uvFrom) {
        return Result.build(itemOpsService.facetCounts(platformType, shopId, keyword, stockThreshold, uvFrom));
    }
}
