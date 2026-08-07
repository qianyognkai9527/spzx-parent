package com.joker.spzx.model.dto.pay;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class RefundCreateDTO {
    @NotBlank(message = "订单号不能为空")
    private String orderNo;
    @NotBlank(message = "退款单号不能为空")
    private String refundNo;
    @NotNull(message = "退款金额不能为空")
    private BigDecimal refundAmount;
    @NotNull(message = "原订单金额不能为空")
    private BigDecimal totalAmount;
    private String reason;
    private Integer payType;
}
