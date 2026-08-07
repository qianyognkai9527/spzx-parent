package com.joker.spzx.manager.pay.strategy.impl;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import com.joker.spzx.manager.pay.config.DouyinPayConfig;
import com.joker.spzx.manager.pay.strategy.AbstractPayStrategy;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.Map;

@Slf4j
@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class DouyinMiniStrategy extends AbstractPayStrategy {

    @Autowired
    private DouyinPayConfig douyinPayConfig;

    @Override
    public PayTypeEnum getPayType() { return PayTypeEnum.DOUYIN_MINI; }

    @Override
    protected PayCreateVO doCreatePayment(PayCreateDTO dto) {
        log.info("[抖音小程序] 创建支付 orderNo={}", dto.getOrderNo());
        PayCreateVO vo = new PayCreateVO();
        vo.setPrepayId("douyin_prepay_" + dto.getOrderNo());
        return vo;
    }

    @Override
    protected PayNotifyResult doHandleNotify(String body) {
        PayNotifyResult result = new PayNotifyResult();
        result.setSuccess(true);
        result.setRawBody(body);
        return result;
    }

    public PayNotifyResult handleNotify(Map<String, String> params) {
        PayNotifyResult result = new PayNotifyResult();
        result.setSuccess("SUCCESS".equals(params.get("status")));
        result.setOrderNo(params.get("cp_orderno"));
        result.setOutTradeNo(params.get("order_id"));
        result.setPayType(getPayType().getCode());
        result.setRawBody(params.toString());
        return result;
    }

    @Override
    protected RefundNotifyResult doHandleRefundNotify(String body) {
        RefundNotifyResult result = new RefundNotifyResult();
        result.setSuccess(true);
        result.setRawBody(body);
        return result;
    }

    @Override
    public PayQueryVO queryPayment(String orderNo) {
        log.info("[抖音] 查询订单 orderNo={}", orderNo);
        return new PayQueryVO();
    }

    @Override
    public void closePayment(String orderNo) {
        log.info("[抖音] 关闭订单 orderNo={}", orderNo);
    }

    @Override
    public void refund(RefundCreateDTO dto) {
        log.info("[抖音] 退款 orderNo={}", dto.getOrderNo());
    }
}
