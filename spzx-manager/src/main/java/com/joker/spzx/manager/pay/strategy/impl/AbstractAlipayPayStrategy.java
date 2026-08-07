package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.alipay.api.AlipayApiException;
import com.alipay.api.AlipayClient;
import com.alipay.api.domain.AlipayTradeCloseModel;
import com.alipay.api.domain.AlipayTradeQueryModel;
import com.alipay.api.domain.AlipayTradeRefundModel;
import com.alipay.api.internal.util.AlipaySignature;
import com.alipay.api.request.AlipayTradeCloseRequest;
import com.alipay.api.request.AlipayTradeQueryRequest;
import com.alipay.api.request.AlipayTradeRefundRequest;
import com.alipay.api.response.AlipayTradeQueryResponse;
import com.alipay.api.response.AlipayTradeRefundResponse;
import com.joker.spzx.manager.pay.config.AlipayConfig;
import com.joker.spzx.manager.pay.strategy.AbstractPayStrategy;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import org.springframework.beans.factory.annotation.Autowired;

import java.math.BigDecimal;
import java.util.Map;

public abstract class AbstractAlipayPayStrategy extends AbstractPayStrategy {

    @Autowired
    protected AlipayClient alipayClient;
    @Autowired
    protected AlipayConfig alipayConfig;

    @Override
    protected PayNotifyResult doHandleNotify(String body) {
        throw new UnsupportedOperationException("支付宝回调请使用 handleNotify(Map) 方法");
    }

    public PayNotifyResult handleNotify(Map<String, String> params) {
        PayNotifyResult result = new PayNotifyResult();
        try {
            boolean signVerified = AlipaySignature.rsaCheckV1(
                    params, alipayConfig.getAlipayPublicKey(), alipayConfig.getCharset(), alipayConfig.getSignType());
            result.setSuccess(signVerified && "TRADE_SUCCESS".equals(params.get("trade_status")));
            result.setOrderNo(params.get("out_trade_no"));
            result.setOutTradeNo(params.get("trade_no"));
            result.setAmount(new BigDecimal(params.getOrDefault("total_amount", "0")));
            result.setPayType(getPayType().getCode());
            result.setRawBody(params.toString());
        } catch (AlipayApiException e) {
            result.setSuccess(false);
            result.setRawBody(params.toString());
        }
        return result;
    }

    @Override
    protected RefundNotifyResult doHandleRefundNotify(String body) {
        throw new UnsupportedOperationException("支付宝退款回调请使用 handleRefundNotify(Map) 方法");
    }

    public RefundNotifyResult handleRefundNotify(Map<String, String> params) {
        RefundNotifyResult result = new RefundNotifyResult();
        result.setSuccess("REFUND_SUCCESS".equals(params.get("refund_status")));
        result.setOrderNo(params.get("out_trade_no"));
        result.setRefundNo(params.get("out_biz_no"));
        result.setRefundAmount(new BigDecimal(params.getOrDefault("refund_amount", "0")));
        result.setPayType(getPayType().getCode());
        result.setRawBody(params.toString());
        return result;
    }

    @Override
    public PayQueryVO queryPayment(String orderNo) {
        try {
            AlipayTradeQueryRequest request = new AlipayTradeQueryRequest();
            AlipayTradeQueryModel model = new AlipayTradeQueryModel();
            model.setOutTradeNo(orderNo);
            request.setBizModel(model);
            AlipayTradeQueryResponse response = alipayClient.execute(request);
            PayQueryVO vo = new PayQueryVO();
            vo.setOrderNo(response.getOutTradeNo());
            vo.setOutTradeNo(response.getTradeNo());
            vo.setTradeStatus(response.getTradeStatus());
            vo.setTotalAmount(new BigDecimal(response.getTotalAmount()));
            return vo;
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝查询失败: " + e.getErrCode() + " " + e.getErrMsg(), e);
        }
    }

    @Override
    public void closePayment(String orderNo) {
        try {
            AlipayTradeCloseRequest request = new AlipayTradeCloseRequest();
            AlipayTradeCloseModel model = new AlipayTradeCloseModel();
            model.setOutTradeNo(orderNo);
            request.setBizModel(model);
            alipayClient.execute(request);
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝关闭订单失败", e);
        }
    }

    @Override
    public void refund(RefundCreateDTO dto) {
        try {
            AlipayTradeRefundRequest request = new AlipayTradeRefundRequest();
            AlipayTradeRefundModel model = new AlipayTradeRefundModel();
            model.setOutTradeNo(dto.getOrderNo());
            model.setRefundAmount(dto.getRefundAmount().toPlainString());
            model.setOutRequestNo(dto.getRefundNo());
            if (dto.getReason() != null) model.setRefundReason(dto.getReason());
            request.setBizModel(model);
            AlipayTradeRefundResponse response = alipayClient.execute(request);
            if (!response.isSuccess()) {
                throw new RuntimeException("支付宝退款失败: " + response.getSubCode() + " " + response.getSubMsg());
            }
        } catch (AlipayApiException e) {
            throw new RuntimeException("支付宝退款失败: " + e.getErrCode() + " " + e.getErrMsg(), e);
        }
    }
}
