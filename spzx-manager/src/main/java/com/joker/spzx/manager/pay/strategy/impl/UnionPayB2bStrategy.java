package com.joker.spzx.manager.pay.strategy.impl;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class UnionPayB2bStrategy extends UnionPayJsapiStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.UNIONPAY_B2B; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        log.info("[银联B2B] 创建企业网银支付 orderNo={}", dto.getOrderNo());
        return super.doCreatePayment(dto);
    }
}
