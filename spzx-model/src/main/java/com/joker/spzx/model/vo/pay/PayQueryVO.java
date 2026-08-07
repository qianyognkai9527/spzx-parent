package com.joker.spzx.model.vo.pay;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class PayQueryVO {
    private String orderNo;
    private String outTradeNo;
    private String tradeStatus;
    private BigDecimal totalAmount;
    private LocalDateTime payTime;
}
