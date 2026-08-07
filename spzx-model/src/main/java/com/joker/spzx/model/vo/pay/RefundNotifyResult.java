package com.joker.spzx.model.vo.pay;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class RefundNotifyResult {
    private boolean success;
    private String orderNo;
    private String refundNo;
    private BigDecimal refundAmount;
    private Integer payType;
    private String rawBody;
}
