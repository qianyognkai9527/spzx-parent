package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 单元逐日趋势（各维度随时间变化，前端勾选画线）。 */
@Data
@Schema(description = "单元逐日趋势")
public class PromoUnitTrendVo {

    @Schema(description = "统计日 yyyy-MM-dd")
    private String statDate;
    private BigDecimal charge;
    private Long adPv;
    private Long click;
    private BigDecimal ctrPercent;
    private BigDecimal cpc;
    private BigDecimal gmvTotal;
    private Integer orderTotal;
    private BigDecimal roi;
    private Integer cartCount;
    private Integer collectTotal;
    private Long crowdClick;
    @Schema(description = "逐日人群点击占比（百分数）")
    private BigDecimal crowdClickShare;
}
