package com.joker.spzx.model.event.pay;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class PayFailedEvent implements Serializable {
    private String orderNo;
    private String channel;
    private String reason;
    private LocalDateTime failTime;

    public static PayFailedEvent of(String orderNo, String channel, String reason) {
        PayFailedEvent event = new PayFailedEvent();
        event.setOrderNo(orderNo);
        event.setChannel(channel);
        event.setReason(reason);
        event.setFailTime(LocalDateTime.now());
        return event;
    }
}
