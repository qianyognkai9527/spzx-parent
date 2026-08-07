package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.alipay.api.AlipayApiException;
import com.alipay.api.domain.AlipayTradePagePayModel;
import com.alipay.api.request.AlipayTradePagePayRequest;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class AlipayPagePayStrategy extends AbstractAlipayPayStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.ALIPAY_PAGE; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            AlipayTradePagePayRequest request = new AlipayTradePagePayRequest();
            request.setNotifyUrl(alipayConfig.getNotifyUrl());
            request.setReturnUrl(alipayConfig.getNotifyUrl().replace("/notify", "/return"));
            AlipayTradePagePayModel model = new AlipayTradePagePayModel();
            model.setOutTradeNo(dto.getOrderNo());
            model.setTotalAmount(dto.getAmount().toPlainString());
            model.setSubject(dto.getSubject());
            model.setProductCode("FAST_INSTANT_TRADE_PAY");
            request.setBizModel(model);
            String form = alipayClient.pageExecute(request).getBody();
            PayCreateVO vo = new PayCreateVO();
            vo.setPayUrl(form);
            return vo;
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝电脑支付创建失败: " + e.getErrCode(), e);
        }
    }
}
