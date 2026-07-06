package com.joker.spzx.model.vo.mall;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "补单统计VO")
public class BrushOrderStatVo {

    @Schema(description = "时间维度标签（如 2026-07 或 2026-W27）")
    private String timeLabel;

    @Schema(description = "商品编号")
    private String productId;

    @Schema(description = "商品标题")
    private String productTitle;

    @Schema(description = "补单总数")
    private Integer totalOrderCount;

    @Schema(description = "已完成单量")
    private Integer completedCount;

    @Schema(description = "未完成单量")
    private Integer uncompletedCount;

    @Schema(description = "未评价单量")
    private Integer unreviewedCount;

    @Schema(description = "总佣金")
    private BigDecimal totalCommission;

    @Schema(description = "已返佣金")
    private BigDecimal paidCommission;

    @Schema(description = "未返佣金")
    private BigDecimal unpaidCommission;

    @Schema(description = "总本金")
    private BigDecimal totalSeedMoney;

    @Schema(description = "总运费")
    private BigDecimal totalWayBillMoney;
}
