package com.joker.spzx.model.vo.mall;

import com.joker.spzx.model.entity.order.OrderSourceRelation;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

@Data
@Schema(description = "报表订单详情VO")
public class ReportOrderVo {

    @Schema(description = "订单ID")
    private Long id;

    @Schema(description = "订单号")
    private String orderId;

    @Schema(description = "实付金额")
    private BigDecimal payMoney;

    @Schema(description = "退款金额")
    private BigDecimal refundMoney;

    @Schema(description = "订单状态")
    private String orderStatus;

    @Schema(description = "订单类型：brush-补单, real-真实订单, unknown-未知")
    private String orderType;

    @Schema(description = "订单类型描述：补单/真实订单/未知")
    private String orderTypeDesc;

    @Schema(description = "关联的货源订单列表")
    private List<OrderSourceRelation> sourceOrders;
}
