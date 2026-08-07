package com.joker.spzx.model.event.pay;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class RefundRequestedEvent implements Serializable {
    private String refundNo;
    private String orderNo;
    private Long merchantId;
    private String channel;
    private BigDecimal refundAmount;
    private BigDecimal totalAmount;
    private String reason;
    private LocalDateTime createTime;

    public static RefundRequestedEvent of(String refundNo, String orderNo, String channel,
                                          BigDecimal refundAmount, BigDecimal totalAmount, String reason) {
        RefundRequestedEvent event = new RefundRequestedEvent();
        event.setRefundNo(refundNo);
        event.setOrderNo(orderNo);
        event.setChannel(channel);
        event.setRefundAmount(refundAmount);
        event.setTotalAmount(totalAmount);
        event.setReason(reason);
        event.setCreateTime(LocalDateTime.now());
        return event;
    }
}
