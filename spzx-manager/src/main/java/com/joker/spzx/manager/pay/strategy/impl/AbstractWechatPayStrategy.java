package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.github.binarywang.wxpay.bean.notify.WxPayNotifyV3Result;
import com.github.binarywang.wxpay.bean.notify.WxPayRefundNotifyV3Result;
import com.github.binarywang.wxpay.bean.request.WxPayRefundV3Request;
import com.github.binarywang.wxpay.service.WxPayService;
import com.joker.spzx.manager.pay.config.WxPayConfig;
import com.joker.spzx.manager.pay.strategy.AbstractPayStrategy;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import org.springframework.beans.factory.annotation.Autowired;

import java.math.BigDecimal;

public abstract class AbstractWechatPayStrategy extends AbstractPayStrategy {

    @Autowired
    protected WxPayService wxPayService;
    @Autowired
    protected WxPayConfig wxPayConfig;

    @Override
    protected PayNotifyResult doHandleNotify(String body) {
        PayNotifyResult notifyResult = new PayNotifyResult();
        try {
            WxPayNotifyV3Result result = wxPayService.parseOrderNotifyV3Result(body, null);
            var data = result.getResult();
            notifyResult.setSuccess("SUCCESS".equals(data.getTradeState()));
            notifyResult.setOrderNo(data.getOutTradeNo());
            notifyResult.setOutTradeNo(data.getTransactionId());
            notifyResult.setAmount(new BigDecimal(data.getAmount().getTotal()).divide(new BigDecimal("100")));
            notifyResult.setPayType(getPayType().getCode());
            notifyResult.setRawBody(body);
        } catch (Exception e) {
            notifyResult.setSuccess(false);
            notifyResult.setRawBody(body);
        }
        return notifyResult;
    }

    @Override
    protected RefundNotifyResult doHandleRefundNotify(String body) {
        RefundNotifyResult result = new RefundNotifyResult();
        try {
            WxPayRefundNotifyV3Result notify = wxPayService.parseRefundNotifyV3Result(body, null);
            var data = notify.getResult();
            result.setSuccess("SUCCESS".equals(data.getRefundStatus()));
            result.setOrderNo(data.getOutTradeNo());
            result.setRefundNo(data.getOutRefundNo());
            result.setRefundAmount(new BigDecimal(data.getAmount().getRefund()).divide(new BigDecimal("100")));
            result.setPayType(getPayType().getCode());
            result.setRawBody(body);
        } catch (Exception e) {
            result.setSuccess(false);
            result.setRawBody(body);
        }
        return result;
    }

    @Override
    public PayQueryVO queryPayment(String orderNo) {
        try {
            var result = wxPayService.queryOrderV3(null, orderNo);
            PayQueryVO vo = new PayQueryVO();
            vo.setOrderNo(result.getOutTradeNo());
            vo.setOutTradeNo(result.getTransactionId());
            vo.setTradeStatus(result.getTradeState());
            vo.setTotalAmount(new BigDecimal(result.getAmount().getTotal()).divide(new BigDecimal("100")));
            return vo;
        } catch (Exception e) {
            throw new RuntimeException("微信支付查询失败: " + e.getMessage(), e);
        }
    }

    @Override
    public void closePayment(String orderNo) {
        try { wxPayService.closeOrderV3(orderNo); } catch (Exception e) { throw new RuntimeException("微信关闭订单失败", e); }
    }

    @Override
    public void refund(RefundCreateDTO dto) {
        try {
            var request = new WxPayRefundV3Request();
            request.setOutTradeNo(dto.getOrderNo());
            request.setOutRefundNo(dto.getRefundNo());
            request.setNotifyUrl(wxPayConfig.getRefundNotifyUrl());
            var amount = new WxPayRefundV3Request.Amount();
            amount.setTotal(dto.getTotalAmount().multiply(new BigDecimal("100")).intValue());
            amount.setRefund(dto.getRefundAmount().multiply(new BigDecimal("100")).intValue());
            request.setAmount(amount);
            wxPayService.refundV3(request);
        } catch (Exception e) { throw new RuntimeException("微信退款失败", e); }
    }
}
