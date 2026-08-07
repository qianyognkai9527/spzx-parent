package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.alipay.api.AlipayApiException;
import com.alipay.api.domain.AlipayTradeAppPayModel;
import com.alipay.api.request.AlipayTradeAppPayRequest;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class AlipayAppPayStrategy extends AbstractAlipayPayStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.ALIPAY_APP; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            AlipayTradeAppPayRequest request = new AlipayTradeAppPayRequest();
            request.setNotifyUrl(alipayConfig.getNotifyUrl());
            AlipayTradeAppPayModel model = new AlipayTradeAppPayModel();
            model.setOutTradeNo(dto.getOrderNo());
            model.setTotalAmount(dto.getAmount().toPlainString());
            model.setSubject(dto.getSubject());
            model.setProductCode("QUICK_MSECURITY_PAY");
            request.setBizModel(model);
            String orderStr = alipayClient.sdkExecute(request).getBody();
            PayCreateVO vo = new PayCreateVO();
            vo.setPayUrl(orderStr);
            return vo;
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝APP支付创建失败: " + e.getErrCode(), e);
        }
    }
}
