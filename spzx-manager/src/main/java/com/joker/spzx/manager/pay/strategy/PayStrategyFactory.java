package com.joker.spzx.manager.pay.strategy;

import com.joker.spzx.model.enums.pay.PayTypeEnum;
import org.springframework.stereotype.Component;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

@Component
public class PayStrategyFactory {

    private final Map<PayTypeEnum, PayStrategy> strategyMap = new EnumMap<>(PayTypeEnum.class);

    public PayStrategyFactory(List<PayStrategy> strategies) {
        for (PayStrategy strategy : strategies) {
            strategyMap.put(strategy.getPayType(), strategy);
        }
    }

    public PayStrategy getStrategy(PayTypeEnum payType) {
        PayStrategy strategy = strategyMap.get(payType);
        if (strategy == null) {
            throw new IllegalArgumentException("不支持的支付方式: " + payType.getDesc());
        }
        return strategy;
    }

    public PayStrategy getStrategy(int payTypeCode) {
        return getStrategy(PayTypeEnum.fromCode(payTypeCode));
    }
}
