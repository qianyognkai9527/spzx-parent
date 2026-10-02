package com.joker.spzx.model.vo.promo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/** 计划维度在区间内的聚合。 */
@Data
@Schema(description = "推广计划区间聚合")
public class PromoPlanVo {

    private String campaignId;

    private String campaignName;

    @Schema(description = "keyword=关键词推广 crowd=人群推广")
    private String planType;

    @Schema(description = "接口 bidType：custom_bid≈标准计划，roi_control≈智能控投产")
    private String bidType;

    @Schema(description = "区间内有数据的天数（少于查询天数=中间有几天没投放）")
    private Integer days;

    private BigDecimal charge;

    private Long adPv;

    private Long click;

    private BigDecimal ctrPercent;

    private BigDecimal cpc;

    private BigDecimal gmvTotal;

    private BigDecimal gmvDirect;

    private Integer orderTotal;

    private BigDecimal roi;

    private Integer cartCount;

    private Integer collectTotal;

    @Schema(description = "最后一次采集时间")
    private String lastCollectedAt;
}
