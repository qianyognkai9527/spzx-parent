package com.joker.spzx.model.vo.pay;

import lombok.Data;

@Data
public class PayCreateVO {
    private String prepayId;
    private String payUrl;
    private String qrCode;
    private String tradeNo;
}
