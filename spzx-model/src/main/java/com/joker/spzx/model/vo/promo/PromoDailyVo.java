package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 推广日报按日趋势的一行（跨计划聚合到"天"）。 */
@Data
@Schema(description = "推广日报按日聚合")
public class PromoDailyVo {

    private String statDate;

    private BigDecimal charge;

    private Long adPv;

    private Long click;

    @Schema(description = "点击率 %，由当天合计重算")
    private BigDecimal ctrPercent;

    @Schema(description = "平均点击花费(元)，由当天合计重算")
    private BigDecimal cpc;

    private BigDecimal gmvTotal;

    @Schema(description = "投入产出比，由当天合计重算")
    private BigDecimal roi;

    private Integer cartCount;

    @Schema(description = "当天有花费的计划数")
    private Integer planCount;
}
