package com.joker.spzx.model.vo.mall;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class BrushPersonStatVo {

    @Schema(description = "刷手Id")
    private Long brushPersonId;

    @Schema(description = "刷手名称")
    private String brushPersonName;

    @Schema(description = "总刷单数")
    private Integer totalOrderCount;

    @Schema(description = "已完成刷单数")
    private Integer completedOrderCount;

    @Schema(description = "总佣金")
    private BigDecimal totalCommission;

    @Schema(description = "已返佣金")
    private BigDecimal paidCommission;

    @Schema(description = "未返佣金")
    private BigDecimal unpaidCommission;

    @Schema(description = "总本金")
    private BigDecimal totalSeedMoney;

    @Schema(description = "未返本金")
    private BigDecimal unpaidSeedMoney;
}
