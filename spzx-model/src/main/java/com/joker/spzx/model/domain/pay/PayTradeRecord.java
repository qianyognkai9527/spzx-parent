package com.joker.spzx.model.domain.pay;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class PayTradeRecord {

    private Long id;
    private String tradeNo;
    private String orderNo;
    private String refundNo;
    private Long merchantId;
    private String channel;
    private String tradeType;
    private BigDecimal amount;
    private BigDecimal fee;
    private Integer result;
    private String channelResp;
    private LocalDateTime createTime;
}
