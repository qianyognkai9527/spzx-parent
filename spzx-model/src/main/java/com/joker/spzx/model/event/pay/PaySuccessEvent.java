package com.joker.spzx.model.event.pay;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class PaySuccessEvent implements Serializable {
    private String orderNo;
    private String outTradeNo;
    private Long merchantId;
    private Integer payType;
    private String channel;
    private BigDecimal amount;
    private BigDecimal fee;
    private String callbackContent;
    private LocalDateTime payTime;

    public static PaySuccessEvent of(String orderNo, String outTradeNo, Integer payType,
                                     String channel, BigDecimal amount, String callbackContent) {
        PaySuccessEvent event = new PaySuccessEvent();
        event.setOrderNo(orderNo);
        event.setOutTradeNo(outTradeNo);
        event.setPayType(payType);
        event.setChannel(channel);
        event.setAmount(amount);
        event.setCallbackContent(callbackContent);
        event.setPayTime(LocalDateTime.now());
        return event;
    }
}
