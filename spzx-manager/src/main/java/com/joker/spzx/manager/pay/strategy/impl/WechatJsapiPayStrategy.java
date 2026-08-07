package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.github.binarywang.wxpay.bean.request.WxPayUnifiedOrderV3Request;
import com.github.binarywang.wxpay.bean.result.WxPayUnifiedOrderV3Result;
import com.github.binarywang.wxpay.bean.result.enums.TradeTypeEnum;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class WechatJsapiPayStrategy extends AbstractWechatPayStrategy {

    @Override
    public PayTypeEnum getPayType() {
        return PayTypeEnum.WECHAT_JSAPI;
    }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            WxPayUnifiedOrderV3Request request = buildBaseRequest(dto);
            WxPayUnifiedOrderV3Request.Payer payer = new WxPayUnifiedOrderV3Request.Payer();
            payer.setOpenid(dto.getOpenid());
            request.setPayer(payer);

            WxPayUnifiedOrderV3Result result = wxPayService.createOrderV3(TradeTypeEnum.JSAPI, request);
            PayCreateVO vo = new PayCreateVO();
            vo.setPrepayId(result.getPrepayId());
            return vo;
        } catch (Exception e) {
            throw new RuntimeException("微信JSAPI支付创建订单失败: " + e.getMessage(), e);
        }
    }

    private WxPayUnifiedOrderV3Request buildBaseRequest(PayCreateDTO dto) {
        WxPayUnifiedOrderV3Request request = new WxPayUnifiedOrderV3Request();
        request.setOutTradeNo(dto.getOrderNo());
        request.setDescription(dto.getSubject());
        request.setNotifyUrl(wxPayConfig.getNotifyUrl());
        WxPayUnifiedOrderV3Request.Amount amount = new WxPayUnifiedOrderV3Request.Amount();
        amount.setTotal(dto.getAmount().multiply(new BigDecimal("100")).intValue());
        request.setAmount(amount);
        return request;
    }
}
