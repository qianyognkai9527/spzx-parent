package com.joker.spzx.manager.pay.strategy.impl;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class AggregateH5Strategy extends AggregateQrStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.AGGREGATE_H5; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        log.info("[聚合H5] 创建支付 orderNo={}", dto.getOrderNo());
        PayCreateVO vo = new PayCreateVO();
        vo.setPayUrl("https://pay.aggregate.com/h5?orderNo=" + dto.getOrderNo());
        return vo;
    }
}
