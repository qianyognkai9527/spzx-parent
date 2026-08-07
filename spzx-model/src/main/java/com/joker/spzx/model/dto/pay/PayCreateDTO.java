package com.joker.spzx.model.dto.pay;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class PayCreateDTO {
    @NotBlank(message = "订单号不能为空")
    private String orderNo;
    @NotNull(message = "支付金额不能为空")
    private BigDecimal amount;
    @NotBlank(message = "商品描述不能为空")
    private String subject;
    @NotNull(message = "支付方式不能为空")
    private Integer payType;
    private String openid;
    private String attach;
}
