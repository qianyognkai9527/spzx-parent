package com.joker.spzx.model.event.pay;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class PayCreatedEvent implements Serializable {
    private String orderNo;
    private String outTradeNo;
    private Long merchantId;
    private Integer payType;
    private String channel;
    private BigDecimal amount;
    private BigDecimal fee;
    private String subject;
    private LocalDateTime createTime;

    public static PayCreatedEvent of(String orderNo, String outTradeNo, Integer payType,
                                     String channel, BigDecimal amount, String subject) {
        PayCreatedEvent event = new PayCreatedEvent();
        event.setOrderNo(orderNo);
        event.setOutTradeNo(outTradeNo);
        event.setPayType(payType);
        event.setChannel(channel);
        event.setAmount(amount);
        event.setSubject(subject);
        event.setCreateTime(LocalDateTime.now());
        return event;
    }
}
