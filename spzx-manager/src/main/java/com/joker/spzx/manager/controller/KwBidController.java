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
 * 一条等式两头都能求：{@code 关键词出价 ×(1+人群溢价) ×分时折扣 ×(1+全能调价) = 实际出价}。
 * 正算给 {@code baseBid}（默认档位：溢价 300%、折扣 50%、调价 0%），反算给 {@code actualBid}
 * （常拿行业平均出价当目标）；另一头留空即可，谁被填谁是已知数。再叠一条利润上限当第二重约束，
 * 两者取小并说清是哪一档在卡脖子。公式与黑箱边界全在 {@link KwBidCalculator}，这里只拆装参数。
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

    /**
     * actualBid 实际出价（这一档真正出出去的价，常拿行业平均出价当目标）；
     * baseBid 关键词出价（后台那一栏填的数）；targetPct 对标系数，100=跟目标持平。
     * **两头至少给一个**：给 actualBid 反推 baseBid，给 baseBid 正算 actualBid。
     * crowds / schedules 不传就按默认一档（溢价 300%、折扣 50%）算。
     */
    public record CalcDto(Double actualBid, Double targetPct, Double swingPct, Double baseBid,
                          List<CrowdDto> crowds, List<ScheduleDto> schedules, TargetDto target) {
    }

    @Operation(summary = "关键词出价↔实际出价双向求解，叠利润上限做第二重约束")
    @PostMapping("/calc")
    public Result<Map<String, Object>> calc(@RequestBody CalcDto dto) {
        try {
            double targetPct = dto.targetPct() == null ? 100 : dto.targetPct();
            double swing = nz(dto.swingPct());
            List<KwBidCalculator.Crowd> crowds = crowds(dto.crowds());
            List<KwBidCalculator.Schedule> schedules = schedules(dto.schedules());
            double goal = dto.actualBid() == null
                    ? forwardGoal(dto, crowds, schedules, swing, targetPct)
                    : KwBidCalculator.money(nz(dto.actualBid()) * targetPct / 100);
            if (goal <= 0) {
                throw new IllegalArgumentException(
                        "实际出价和关键词出价至少给一个 —— 这条等式两头总得填一头");
            }
            KwBidCalculator.Target target = target(dto.target());
            Double cpcCeiling = target == null ? null : cpcCeiling(dto.target(), target);

            // 第一遍：只反推档位上限（哪一档最紧）
            Double goalSafeBase = null;
            Double profitSafeBase = null;
            String goalBinding = "";
            String profitBinding = "";
            for (var crowd : crowds) {
                for (var schedule : schedules) {
                    if (KwBidCalculator.notServing(schedule.discountPct())) {
                        continue;
                    }
                    double allowed = KwBidCalculator.money(KwBidCalculator.maxBaseBid(
                            goal, crowd.premiumPct(), schedule.discountPct(), swing));
                    if (goalSafeBase == null || allowed < goalSafeBase) {
                        goalSafeBase = allowed;
                        goalBinding = crowd.name() + ' ' + schedule.label();
                    }
                    if (cpcCeiling != null) {
                        double pAllowed = KwBidCalculator.money(KwBidCalculator.maxBaseBid(
                                cpcCeiling, crowd.premiumPct(), schedule.discountPct(), swing));
                        if (profitSafeBase == null || pAllowed < profitSafeBase) {
                            profitSafeBase = pAllowed;
                            profitBinding = crowd.name() + ' ' + schedule.label();
                        }
                    }
                }
            }

            // 第二遍：矩阵按"我打算填的关键词出价"展开；没填就按反推值展开，表里永远是一组自洽的数
            double shownBase = dto.baseBid() == null ? (goalSafeBase == null ? 0 : goalSafeBase) : dto.baseBid();
            var matrix = KwBidCalculator.matrix(shownBase, crowds, schedules, swing);
            List<Map<String, Object>> cells = new ArrayList<>();
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
                row.put("allowedBaseBid", cell.notServing() ? null : KwBidCalculator.money(
                        KwBidCalculator.maxBaseBid(goal, cell.premiumPct(), cell.discountPct(), swing)));
                row.put("profitAllowedBaseBid", cell.notServing() || cpcCeiling == null ? null
                        : KwBidCalculator.money(KwBidCalculator.maxBaseBid(
                                cpcCeiling, cell.premiumPct(), cell.discountPct(), swing)));
                row.put("overGoal", !cell.notServing() && cell.high() > goal + 0.001);
                row.put("overProfit", !cell.notServing() && cpcCeiling != null && cell.high() > cpcCeiling + 0.001);
                cells.add(row);
            }

            Double advice = goalSafeBase;
            String adviceSource = "目标实际出价";
            if (profitSafeBase != null && (goalSafeBase == null || profitSafeBase < goalSafeBase)) {
                advice = profitSafeBase;
                adviceSource = "利润上限";
            }

            Map<String, Object> out = new LinkedHashMap<>();
            out.put("actualBid", goal);
            out.put("solvedFrom", dto.actualBid() != null ? "actualBid" : "baseBid");
            out.put("targetPct", targetPct);
            out.put("goalBid", goal);
            out.put("swingPct", swing);
            out.put("baseBid", KwBidCalculator.money(shownBase));
            out.put("recommendedBaseBid", goalSafeBase);
            out.put("recommendedBinding", goalBinding);
            out.put("maxHigh", matrix.maxHigh());
            // 正数＝按现在填的出价还留着余地，负数＝已经顶破目标价。前端据此出判据，不自己比大小
            out.put("goalGap", KwBidCalculator.signedMoney(goal - matrix.maxHigh()));
            out.put("ceilingGap",
                    cpcCeiling == null ? null
                            : KwBidCalculator.signedMoney(cpcCeiling - matrix.maxHigh()));
            out.put("cpcCeiling", cpcCeiling == null ? null : KwBidCalculator.money(cpcCeiling));
            out.put("profitBaseBid", profitSafeBase);
            out.put("profitBinding", profitBinding);
            out.put("adviceBaseBid", advice);
            out.put("adviceSource", adviceSource);
            out.put("cells", cells);
            out.put("target", target);
            return Result.build(out);
        } catch (IllegalArgumentException e) {
            // 这里的 message 全部由 KwBidCalculator 的校验自己拼，不含用户输入与请求体原文
            return Result.build(null, 400, "参数不合法：" + e.getMessage());
        }
    }

    /**
     * 只给了关键词出价（正算方向）时，目标实际出价就是它乘完整条链的结果 ——
     * 多档取最紧的那一档（= 最高的实际上限），口径与反推那条路一致。
     */
    private static double forwardGoal(CalcDto dto, List<KwBidCalculator.Crowd> crowds,
                                      List<KwBidCalculator.Schedule> schedules,
                                      double swing, double targetPct) {
        double base = nz(dto.baseBid());
        if (base <= 0) {
            return 0;
        }
        double high = KwBidCalculator.matrix(base, crowds, schedules, swing).maxHigh();
        return KwBidCalculator.money(high * targetPct / 100);
    }

    /** 一档都不给时按默认档位算：溢价 300%（后台能设的最高档） */
    private List<KwBidCalculator.Crowd> crowds(List<CrowdDto> in) {
        if (in == null || in.isEmpty()) {
            return List.of(new KwBidCalculator.Crowd("人群溢价", 300));
        }
        List<KwBidCalculator.Crowd> out = new ArrayList<>();
        for (CrowdDto c : in) {
            String name = c.name() == null || c.name().isBlank() ? "人群" + (out.size() + 1) : c.name().trim();
            out.add(new KwBidCalculator.Crowd(name, c.premiumPct() == null ? 0 : c.premiumPct()));
        }
        return out;
    }

    /** 同理默认一档：分时折扣 50% */
    private List<KwBidCalculator.Schedule> schedules(List<ScheduleDto> in) {
        if (in == null || in.isEmpty()) {
            return List.of(new KwBidCalculator.Schedule("分时折扣", 50));
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
            throw new IllegalArgumentException("利润口径要么整份给（客单价+转化率），要么带一个宝贝进来");
        }
        return new KwBidCalculator.Target(in.unitPrice(), in.convRatePct(), nz(in.unitMargin()));
    }

    private double cpcCeiling(TargetDto in, KwBidCalculator.Target t) {
        if ("margin".equals(in.mode())) {
            if (t.unitMargin() <= 0) {
                throw new IllegalArgumentException("按毛利分成反推需要每单毛利（商品运营台的 margin 列，不含运费）");
            }
            return KwBidCalculator.cpcCeilingByMargin(t.unitMargin(), t.convRatePct(),
                    share(in.marginSharePct(), "毛利投入比例"));
        }
        return KwBidCalculator.cpcCeilingByFeeRate(t.unitPrice(), t.convRatePct(),
                share(in.feeRatePct(), "可承受推广费率"));
    }

    /** 比例没填就当 0 —— 反推不出上限比凭空给一个上限安全 */
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
