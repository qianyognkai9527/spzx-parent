package com.joker.spzx.manager.service;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;

public interface PaymentService {
    PayCreateVO createPayment(PayCreateDTO dto);
    PayNotifyResult handleWechatNotify(String body);
    PayNotifyResult handleAlipayNotify(java.util.Map<String, String> params);
    RefundNotifyResult handleWechatRefundNotify(String body);
    RefundNotifyResult handleAlipayRefundNotify(java.util.Map<String, String> params);
    PayQueryVO queryPayment(String orderNo, Integer payType);
    void closePayment(String orderNo, Integer payType);
    void refund(RefundCreateDTO dto);
}
