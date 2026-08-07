package com.joker.spzx.manager.pay.strategy.impl;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class UnionPayQrStrategy extends UnionPayJsapiStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.UNIONPAY_QR; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        log.info("[银联二维码] 创建扫码支付 orderNo={}", dto.getOrderNo());
        PayCreateVO vo = new PayCreateVO();
        vo.setQrCode("unionpay://qr?orderNo=" + dto.getOrderNo());
        return vo;
    }
}
