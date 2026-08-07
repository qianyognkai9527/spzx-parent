package com.joker.spzx.manager.pay.strategy.impl;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class LakalaQrStrategy extends LakalaPosStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.LAKALA_QR; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        log.info("[拉卡拉扫码] 创建支付 orderNo={}", dto.getOrderNo());
        PayCreateVO vo = new PayCreateVO();
        vo.setQrCode("lakala://qr?orderNo=" + dto.getOrderNo());
        return vo;
    }
}
