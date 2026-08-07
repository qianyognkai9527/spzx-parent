package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.alipay.api.AlipayApiException;
import com.alipay.api.domain.AlipayTradeWapPayModel;
import com.alipay.api.request.AlipayTradeWapPayRequest;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class AlipayWapPayStrategy extends AbstractAlipayPayStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.ALIPAY_WAP; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            AlipayTradeWapPayRequest request = new AlipayTradeWapPayRequest();
            request.setNotifyUrl(alipayConfig.getNotifyUrl());
            request.setReturnUrl(alipayConfig.getNotifyUrl().replace("/notify", "/return"));
            AlipayTradeWapPayModel model = new AlipayTradeWapPayModel();
            model.setOutTradeNo(dto.getOrderNo());
            model.setTotalAmount(dto.getAmount().toPlainString());
            model.setSubject(dto.getSubject());
            model.setProductCode("QUICK_WAP_WAY");
            request.setBizModel(model);
            String form = alipayClient.pageExecute(request).getBody();
            PayCreateVO vo = new PayCreateVO();
            vo.setPayUrl(form);
            return vo;
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝手机网站支付创建失败: " + e.getErrCode(), e);
        }
    }
}
