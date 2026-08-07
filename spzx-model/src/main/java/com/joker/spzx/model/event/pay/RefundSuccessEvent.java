package com.joker.spzx.model.event.pay;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class RefundSuccessEvent implements Serializable {
    private String refundNo;
    private String orderNo;
    private Long merchantId;
    private String channel;
    private BigDecimal refundAmount;
    private String callbackContent;
    private LocalDateTime refundTime;

    public static RefundSuccessEvent of(String refundNo, String orderNo, String channel,
                                        BigDecimal refundAmount, String callbackContent) {
        RefundSuccessEvent event = new RefundSuccessEvent();
        event.setRefundNo(refundNo);
        event.setOrderNo(orderNo);
        event.setChannel(channel);
        event.setRefundAmount(refundAmount);
        event.setCallbackContent(callbackContent);
        event.setRefundTime(LocalDateTime.now());
        return event;
    }
}
