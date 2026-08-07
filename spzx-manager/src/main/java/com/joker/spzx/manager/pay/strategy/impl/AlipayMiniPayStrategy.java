package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.alipay.api.AlipayApiException;
import com.alipay.api.domain.AlipayTradeCreateModel;
import com.alipay.api.request.AlipayTradeCreateRequest;
import com.alipay.api.response.AlipayTradeCreateResponse;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class AlipayMiniPayStrategy extends AbstractAlipayPayStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.ALIPAY_MINI; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            AlipayTradeCreateRequest request = new AlipayTradeCreateRequest();
            request.setNotifyUrl(alipayConfig.getNotifyUrl());
            AlipayTradeCreateModel model = new AlipayTradeCreateModel();
            model.setOutTradeNo(dto.getOrderNo());
            model.setTotalAmount(dto.getAmount().toPlainString());
            model.setSubject(dto.getSubject());
            model.setBuyerId(dto.getOpenid());
            request.setBizModel(model);
            AlipayTradeCreateResponse response = alipayClient.execute(request);
            PayCreateVO vo = new PayCreateVO();
            vo.setTradeNo(response.getTradeNo());
            return vo;
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝小程序支付创建失败: " + e.getErrCode(), e);
        }
    }
}
