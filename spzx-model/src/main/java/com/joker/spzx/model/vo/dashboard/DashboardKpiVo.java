package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "仪表盘KPI卡片数据")
public class DashboardKpiVo {

    @Schema(description = "订单总数")
    private Long orderCount;

    @Schema(description = "订单总金额")
    private BigDecimal orderTotalAmount;

    @Schema(description = "货源工厂数")
    private Long factoryCount;

    @Schema(description = "货源商品数")
    private Long productCount;
}
