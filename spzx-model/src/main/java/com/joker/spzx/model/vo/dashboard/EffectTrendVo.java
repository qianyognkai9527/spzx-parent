package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "商品效果趋势点（一次生意参谋快照 = 一个点，值为该快照覆盖的近7日汇总）")
public class EffectTrendVo {

    @Schema(description = "快照时间")
    private String snapshotTime;

    @Schema(description = "该次快照覆盖的商品数")
    private Integer items;

    @Schema(description = "近7日访客数合计（已剔除异常流量商品）")
    private Long visitors;

    @Schema(description = "近7日成交金额合计")
    private BigDecimal payAmount;

    @Schema(description = "近7日加购人数合计")
    private Long cartUsers;

    @Schema(description = "被判为异常流量的商品数：访客≥100 且 跳失率>80% 且 近7日零成交")
    private Long abnormalItems;

    @Schema(description = "上述异常流量商品贡献的访客数，未计入 visitors")
    private Long abnormalVisitors;
}
