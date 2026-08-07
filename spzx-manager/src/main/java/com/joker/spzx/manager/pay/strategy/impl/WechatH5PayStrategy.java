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
public class WechatH5PayStrategy extends AbstractWechatPayStrategy {

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.WECHAT_H5; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        try {
            WxPayUnifiedOrderV3Request request = new WxPayUnifiedOrderV3Request();
            request.setOutTradeNo(dto.getOrderNo());
            request.setDescription(dto.getSubject());
            request.setNotifyUrl(wxPayConfig.getNotifyUrl());
            WxPayUnifiedOrderV3Request.Amount amount = new WxPayUnifiedOrderV3Request.Amount();
            amount.setTotal(dto.getAmount().multiply(new BigDecimal("100")).intValue());
            request.setAmount(amount);
            WxPayUnifiedOrderV3Request.SceneInfo sceneInfo = new WxPayUnifiedOrderV3Request.SceneInfo();
            sceneInfo.setPayerClientIp("127.0.0.1");
            WxPayUnifiedOrderV3Request.H5Info h5Info = new WxPayUnifiedOrderV3Request.H5Info();
            h5Info.setType("Wap");
            sceneInfo.setH5Info(h5Info);
            request.setSceneInfo(sceneInfo);

            WxPayUnifiedOrderV3Result result = wxPayService.createOrderV3(TradeTypeEnum.H5, request);
            PayCreateVO vo = new PayCreateVO();
            vo.setPayUrl(result.getH5Url());
            return vo;
        } catch (Exception e) {
            throw new RuntimeException("微信H5支付创建订单失败: " + e.getMessage(), e);
        }
    }
}
