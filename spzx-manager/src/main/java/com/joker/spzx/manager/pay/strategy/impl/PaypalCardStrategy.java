package com.joker.spzx.manager.pay.strategy.impl;

import com.joker.spzx.model.enums.pay.PayTypeEnum;
import org.springframework.stereotype.Component;

@Component
public class PaypalCardStrategy extends PaypalOrderStrategy {
    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.PAYPAL_CARD; }
}
