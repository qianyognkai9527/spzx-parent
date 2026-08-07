package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.alipay.api.AlipayApiException;
import com.alipay.api.domain.AlipayTradePrecreateModel;
import com.alipay.api.request.AlipayTradePrecreateRequest;
import com.alipay.api.response.AlipayTradePrecreateResponse;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class AlipayScanPayStrategy extends AbstractAlipayPayStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.ALIPAY_SCAN; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            AlipayTradePrecreateRequest request = new AlipayTradePrecreateRequest();
            request.setNotifyUrl(alipayConfig.getNotifyUrl());
            AlipayTradePrecreateModel model = new AlipayTradePrecreateModel();
            model.setOutTradeNo(dto.getOrderNo());
            model.setTotalAmount(dto.getAmount().toPlainString());
            model.setSubject(dto.getSubject());
            request.setBizModel(model);
            AlipayTradePrecreateResponse response = alipayClient.execute(request);
            PayCreateVO vo = new PayCreateVO();
            vo.setQrCode(response.getQrCode());
            return vo;
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝扫码支付创建失败: " + e.getErrCode(), e);
        }
    }
}
