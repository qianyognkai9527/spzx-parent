package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.promo.PromoReportService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.promo.PromoDailyVo;
import com.joker.spzx.model.vo.promo.PromoItemVo;
import com.joker.spzx.model.vo.promo.PromoPlanVo;
import com.joker.spzx.model.vo.promo.PromoSummaryVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 推广日报看板：区间汇总、按日趋势、计划维度、宝贝维度。全部只读。
 *
 * 数据由 automation/tb-auto/collect_alimama_promo.py 每天 22:00 采集（LaunchAgent），
 * 只取昨天及更早，所以不传日期时默认区间是「昨天往前 14 天」。
 */
@RestController
@Tag(name = "推广日报看板", description = "万相台推广花费的计划/宝贝维度只读聚合")
@RequestMapping("/admin/promo/report")
public class PromoReportController {

    @Autowired
    private PromoReportService promoReportService;

    @Operation(summary = "区间汇总卡片（比率按汇总分子分母重算）")
    @GetMapping("/summary")
    public Result<PromoSummaryVo> summary(@RequestParam(required = false) String from,
                                          @RequestParam(required = false) String to,
                                          @RequestParam(required = false, defaultValue = "all") String planType) {
        return Result.build(promoReportService.summary(from, to, planType));
    }

    @Operation(summary = "按日趋势")
    @GetMapping("/trend")
    public Result<List<PromoDailyVo>> trend(@RequestParam(required = false) String from,
                                            @RequestParam(required = false) String to,
                                            @RequestParam(required = false, defaultValue = "all") String planType) {
        return Result.build(promoReportService.trend(from, to, planType));
    }

    @Operation(summary = "计划维度区间聚合")
    @GetMapping("/plans")
    public Result<List<PromoPlanVo>> plans(@RequestParam(required = false) String from,
                                           @RequestParam(required = false) String to,
                                           @RequestParam(required = false, defaultValue = "all") String planType) {
        return Result.build(promoReportService.plans(from, to, planType));
    }

    @Operation(summary = "宝贝维度分页；facet 可选 all/noDeal(花钱不出单)/orphan(本地无此商品)/unpriced(投着但未定价)")
    @GetMapping("/items/{pageNum}/{pageSize}")
    public Result<IPage<PromoItemVo>> items(@PathVariable long pageNum,
                                            @PathVariable long pageSize,
                                            @RequestParam(required = false) String from,
                                            @RequestParam(required = false) String to,
                                            @RequestParam(required = false, defaultValue = "all") String planType,
                                            @RequestParam(required = false) String campaignId,
                                            @RequestParam(required = false) String keyword,
                                            @RequestParam(required = false, defaultValue = "all") String facet,
                                            @RequestParam(required = false, defaultValue = "charge") String sort) {
        return Result.build(promoReportService.items(pageNum, pageSize, from, to,
                planType, campaignId, keyword, facet, sort));
    }

    @Operation(summary = "宝贝维度各筛选项条数（与分页同一套口径）")
    @GetMapping("/itemFacetCounts")
    public Result<Map<String, Object>> itemFacetCounts(@RequestParam(required = false) String from,
                                                       @RequestParam(required = false) String to,
                                                       @RequestParam(required = false, defaultValue = "all") String planType,
                                                       @RequestParam(required = false) String campaignId,
                                                       @RequestParam(required = false) String keyword) {
        return Result.build(promoReportService.itemFacetCounts(from, to, planType, campaignId, keyword));
    }
}
