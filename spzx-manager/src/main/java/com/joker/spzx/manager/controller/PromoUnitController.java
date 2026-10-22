package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.promo.PromoUnitService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.promo.PromoUnitCrowdVo;
import com.joker.spzx.model.vo.promo.PromoUnitKeywordVo;
import com.joker.spzx.model.vo.promo.PromoUnitTrendVo;
import com.joker.spzx.model.vo.promo.PromoUnitVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** 推广·单元日报（只读）。campaignId 必填（页面计划下拉），unitId 除 units 外必填。 */
@RestController
@Tag(name = "推广单元日报", description = "万相台标准计划单元级只读下钻（关键词明细/人群点击占比）")
@RequestMapping("/admin/promo/unit")
public class PromoUnitController {

    @Autowired
    private PromoUnitService promoUnitService;

    @Operation(summary = "单元列表（占比=人群点击/总点击，先加总再除，分母0出null）")
    @GetMapping("/units")
    public Result<List<PromoUnitVo>> units(@RequestParam String campaignId,
                                           @RequestParam(required = false) String from,
                                           @RequestParam(required = false) String to,
                                           @RequestParam(required = false, defaultValue = "charge") String sort) {
        return Result.build(promoUnitService.units(from, to, campaignId, sort));
    }

    @Operation(summary = "单元逐日全指标趋势（含逐日人群占比）")
    @GetMapping("/trend")
    public Result<List<PromoUnitTrendVo>> trend(@RequestParam String campaignId,
                                                @RequestParam String unitId,
                                                @RequestParam(required = false) String from,
                                                @RequestParam(required = false) String to) {
        return Result.build(promoUnitService.trend(from, to, campaignId, unitId));
    }

    @Operation(summary = "单元关键词明细（词/点击/均价/花费/收藏/加购/成交单数/成交金额/ROI）")
    @GetMapping("/keywords")
    public Result<List<PromoUnitKeywordVo>> keywords(@RequestParam String campaignId,
                                                     @RequestParam String unitId,
                                                     @RequestParam(required = false) String from,
                                                     @RequestParam(required = false) String to,
                                                     @RequestParam(required = false, defaultValue = "charge") String sort) {
        return Result.build(promoUnitService.keywords(from, to, campaignId, unitId, sort));
    }

    @Operation(summary = "单元人群明细（含人群点击占比与差额=泛流量口径）")
    @GetMapping("/crowds")
    public Result<List<PromoUnitCrowdVo>> crowds(@RequestParam String campaignId,
                                                 @RequestParam String unitId,
                                                 @RequestParam(required = false) String from,
                                                 @RequestParam(required = false) String to) {
        return Result.build(promoUnitService.crowds(from, to, campaignId, unitId));
    }
}
