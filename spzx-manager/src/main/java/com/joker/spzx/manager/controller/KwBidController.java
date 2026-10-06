package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.kw.KwBidCalculator;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 关键词推广（标准计划）出价计算 —— 纯算术，不碰库、不花钱。
 *
 * 出价链条与黑箱边界都写在 {@link KwBidCalculator} 里，这个类只做参数拆装：
 * 前端填的是"百分比数字"（30 = +30%），人群和时段可以给多组，反推口径二选一
 * （按推广费率 / 按毛利分成），也可以直接带一个商品运营台的宝贝进来（客单价取成交均价）。
 */
@Slf4j
@RestController
@RequestMapping("/admin/kw/bid")
@Tag(name = "关键词出价计算")
public class KwBidController {

    public record CrowdDto(String name, Double premiumPct) {
    }

    public record ScheduleDto(String label, Double discountPct) {
    }

    public record ItemDto(Double payAmount, Integer payBuyers, Long visitors,
                          Double unitMargin, Integer abnormalTraffic) {
    }

    /** mode: feeRate（按可承受推广费率）| margin（按每单毛利分成）*/
    public record TargetDto(String mode, Double unitPrice, Double convRatePct, Double unitMargin,
                            Double feeRatePct, Double marginSharePct, ItemDto item) {
    }

    public record CalcDto(Double baseBid, Double swingPct, List<CrowdDto> crowds,
                          List<ScheduleDto> schedules, TargetDto target) {
    }

    @Operation(summary = "算出人群×时段的出价区间，并按目标口径反推关键词出价上限")
    @PostMapping("/calc")
    public Result<Map<String, Object>> calc(@RequestBody CalcDto dto) {
        try {
            List<KwBidCalculator.Crowd> crowds = crowds(dto.crowds());
            List<KwBidCalculator.Schedule> schedules = schedules(dto.schedules());
            double swing = dto.swingPct() == null ? 0 : dto.swingPct();
            double base = dto.baseBid() == null ? 0 : dto.baseBid();
            if (base <= 0 && dto.target() == null) {
                throw new IllegalArgumentException("关键词出价要填，或者至少要填反推目标（客单价/转化率）");
            }

            KwBidCalculator.Matrix matrix = KwBidCalculator.matrix(base, crowds, schedules, swing);
            KwBidCalculator.Target target = target(dto.target());
            Double cpcCeiling = target == null ? null : cpcCeiling(dto.target(), target);

            List<Map<String, Object>> cells = new ArrayList<>();
            Double safeBase = null;
            for (var cell : matrix.cells()) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("crowd", cell.crowd());
                row.put("schedule", cell.schedule());
                row.put("premiumPct", cell.premiumPct());
                row.put("discountPct", cell.discountPct());
                row.put("certain", cell.certain());
                row.put("low", cell.low());
                row.put("high", cell.high());
                row.put("notServing", cell.notServing());
                if (cpcCeiling != null && !cell.notServing()) {
                    double allowed = KwBidCalculator.money(KwBidCalculator.maxBaseBid(
                            cpcCeiling, cell.premiumPct(), cell.discountPct(), swing));
                    row.put("allowedBaseBid", allowed);
                    // 能覆盖所有人群×时段的安全基数 = 各格上限里最小的那个
                    if (safeBase == null || allowed < safeBase) {
                        safeBase = allowed;
                    }
                } else {
                    row.put("allowedBaseBid", null);
                }
                cells.add(row);
            }

            Map<String, Object> out = new LinkedHashMap<>();
            out.put("baseBid", KwBidCalculator.money(base));
            out.put("swingPct", swing);
            out.put("cells", cells);
            out.put("maxHigh", matrix.maxHigh());
            out.put("cpcCeiling", cpcCeiling == null ? null : KwBidCalculator.money(cpcCeiling));
            out.put("safeBaseBid", safeBase);
            out.put("target", target);
            return Result.build(out);
        } catch (IllegalArgumentException e) {
            // 这里的 message 全部由 KwBidCalculator 的校验自己拼，不含用户输入与请求体原文
            return Result.build(null, 400, "参数不合法：" + e.getMessage());
        }
    }

    private List<KwBidCalculator.Crowd> crowds(List<CrowdDto> in) {
        if (in == null || in.isEmpty()) {
            return List.of(new KwBidCalculator.Crowd("不溢价", 0));
        }
        List<KwBidCalculator.Crowd> out = new ArrayList<>();
        for (CrowdDto c : in) {
            String name = c.name() == null || c.name().isBlank() ? "人群" + (out.size() + 1) : c.name().trim();
            out.add(new KwBidCalculator.Crowd(name, c.premiumPct() == null ? 0 : c.premiumPct()));
        }
        return out;
    }

    private List<KwBidCalculator.Schedule> schedules(List<ScheduleDto> in) {
        if (in == null || in.isEmpty()) {
            return List.of(new KwBidCalculator.Schedule("全天 00-24", 100));
        }
        List<KwBidCalculator.Schedule> out = new ArrayList<>();
        for (ScheduleDto s : in) {
            String label = s.label() == null || s.label().isBlank() ? "时段" + (out.size() + 1) : s.label().trim();
            out.add(new KwBidCalculator.Schedule(label, s.discountPct() == null ? 100 : s.discountPct()));
        }
        return out;
    }

    private KwBidCalculator.Target target(TargetDto in) {
        if (in == null) {
            return null;
        }
        if (in.item() != null) {
            var item = in.item();
            return KwBidCalculator.targetFromItem(new KwBidCalculator.ItemInputs(
                    nz(item.payAmount()), nzi(item.payBuyers()), nzl(item.visitors()),
                    nz(item.unitMargin()), Integer.valueOf(1).equals(item.abnormalTraffic())));
        }
        if (in.unitPrice() == null || in.convRatePct() == null) {
            throw new IllegalArgumentException("反推目标要么整份给（客单价+转化率），要么带一个宝贝进来");
        }
        return new KwBidCalculator.Target(in.unitPrice(), in.convRatePct(), nz(in.unitMargin()));
    }

    private double cpcCeiling(TargetDto in, KwBidCalculator.Target t) {
        if ("margin".equals(in.mode())) {
            if (t.unitMargin() <= 0) {
                throw new IllegalArgumentException("按毛利分成反推需要每单毛利（商品运营台的 margin 列，不含运费）");
            }
            return KwBidCalculator.cpcCeilingByMargin(t.unitMargin(), t.convRatePct(), share(in.marginSharePct(), "毛利投入比例"));
        }
        return KwBidCalculator.cpcCeilingByFeeRate(t.unitPrice(), t.convRatePct(), share(in.feeRatePct(), "可承受推广费率"));
    }

    /** 比例没填就当 0 —— 反推不出上限比给一个凭空假设的上限安全 */
    private static double share(Double v, String what) {
        if (v == null) {
            throw new IllegalArgumentException("请填写" + what);
        }
        return v;
    }

    private static double nz(Double v) {
        return v == null ? 0 : v;
    }

    private static int nzi(Integer v) {
        return v == null ? 0 : v;
    }

    private static long nzl(Long v) {
        return v == null ? 0 : v;
    }
}
