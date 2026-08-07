package com.joker.spzx.model.vo.pay;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class PayNotifyResult {
    private boolean success;
    private String orderNo;
    private String outTradeNo;
    private BigDecimal amount;
    private Integer payType;
    private String attach;
    private String rawBody;
}
