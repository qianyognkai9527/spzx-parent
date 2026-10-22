package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 单元 × 人群明细（dimension='crowd'）。占比 = 该人群点击 / 该单元总点击。 */
@Data
@Schema(description = "单元人群明细")
public class PromoUnitCrowdVo {

    private String crowdId;
    private String crowdName;
    @Schema(description = "区间内有数据的天数")
    private Integer days;
    private Long click;
    private BigDecimal charge;
    @Schema(description = "该单元区间总点击（每行都带，供 service 算占比）")
    private Long unitClick;
    @Schema(description = "人群点击占比 = click / unitClick × 100（百分数）；unitClick=0 为 null")
    private BigDecimal crowdClickShare;
}
