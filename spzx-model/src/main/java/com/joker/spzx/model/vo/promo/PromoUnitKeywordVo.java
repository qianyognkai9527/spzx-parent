package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 单元 × 关键词明细（词层报表，dimension='keyword'）。 */
@Data
@Schema(description = "单元关键词明细")
public class PromoUnitKeywordVo {

    @Schema(description = "关键词文本")
    private String keyword;
    @Schema(description = "平台词 id（平台没给就为 null）")
    private String bidwordId;
    @Schema(description = "区间内有数据的天数")
    private Integer days;
    private BigDecimal charge;
    private Long click;
    @Schema(description = "平均点击单价")
    private BigDecimal cpc;
    private BigDecimal gmvTotal;
    private Integer orderTotal;
    private BigDecimal roi;
    private Integer cartCount;
    private Integer collectTotal;
}
