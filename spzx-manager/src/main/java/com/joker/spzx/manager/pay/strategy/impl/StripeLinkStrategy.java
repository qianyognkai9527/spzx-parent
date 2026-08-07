package com.joker.spzx.manager.pay.strategy.impl;

import com.joker.spzx.model.enums.pay.PayTypeEnum;
import org.springframework.stereotype.Component;

@Component
public class StripeLinkStrategy extends StripeCardStrategy {
    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.STRIPE_LINK; }
}
