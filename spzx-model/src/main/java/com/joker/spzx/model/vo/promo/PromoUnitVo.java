package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 单元维度推广区间聚合（推广·单元日报页）。
 * 占比不在 SQL 里算 —— SQL 只出分子 crowdClick 与分母 click，service 先加总再除。
 */
@Data
@Schema(description = "单元维度推广区间聚合")
public class PromoUnitVo {

    private String unitId;
    @Schema(description = "单元名（关键词推广里单元=宝贝，即商品标题）")
    private String unitName;
    private String campaignId;
    private String campaignName;
    @Schema(description = "区间内有数据的天数")
    private Integer days;
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
    @Schema(description = "该单元各人群点击之和（只有采了人群层的计划有值）；null=没有人群数据")
    private Long crowdClick;
    @Schema(description = "人群点击占比 = 人群点击 / 总点击 × 100（百分数）；click=0 或无人群数据为 null")
    private BigDecimal crowdClickShare;
}
