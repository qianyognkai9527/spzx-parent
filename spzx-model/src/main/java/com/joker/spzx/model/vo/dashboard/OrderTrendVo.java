package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

@Data
@Schema(description = "订单趋势数据")
public class OrderTrendVo {

    @Schema(description = "日期")
    private String date;

    @Schema(description = "订单数")
    private Integer orderCount;

    @Schema(description = "订单金额")
    private BigDecimal orderAmount;
}
