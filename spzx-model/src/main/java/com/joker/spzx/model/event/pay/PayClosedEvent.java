package com.joker.spzx.model.event.pay;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class PayClosedEvent implements Serializable {
    private String orderNo;
    private String channel;
    private LocalDateTime closeTime;

    public static PayClosedEvent of(String orderNo, String channel) {
        PayClosedEvent event = new PayClosedEvent();
        event.setOrderNo(orderNo);
        event.setChannel(channel);
        event.setCloseTime(LocalDateTime.now());
        return event;
    }
}
