package com.joker.spzx.manager.pay.strategy;

import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;

public interface PayStrategy {
    PayTypeEnum getPayType();
    PayCreateVO createPayment(PayCreateDTO dto);
    PayNotifyResult handleNotify(String body);
    RefundNotifyResult handleRefundNotify(String body);
    PayQueryVO queryPayment(String orderNo);
    void closePayment(String orderNo);
    void refund(RefundCreateDTO dto);
}
