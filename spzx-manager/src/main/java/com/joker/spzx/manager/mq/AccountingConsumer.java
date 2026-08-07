package com.joker.spzx.manager.mq;

import com.joker.spzx.model.event.pay.PaySuccessEvent;
import com.joker.spzx.model.event.pay.RefundSuccessEvent;
import lombok.extern.slf4j.Slf4j;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
@RocketMQMessageListener(
    topic = PayEventProducer.TOPIC_PAY,
    consumerGroup = "accounting_group",
    selectorExpression = PayEventProducer.TAG_PAY_SUCCESS + " || " + PayEventProducer.TAG_REFUND_SUCCESS
)
public class AccountingConsumer implements RocketMQListener<String> {

    @Override
    public void onMessage(String message) {
        try {
            if (message.contains("refundNo")) {
                RefundSuccessEvent event = com.alibaba.fastjson.JSON.parseObject(message, RefundSuccessEvent.class);
                handleRefundAccounting(event);
            } else {
                PaySuccessEvent event = com.alibaba.fastjson.JSON.parseObject(message, PaySuccessEvent.class);
                handlePayAccounting(event);
            }
        } catch (Exception e) {
            log.error("记账消费失败 message={}", message, e);
        }
    }

    private void handlePayAccounting(PaySuccessEvent event) {
        log.info("[记账] 支付成功记账 orderNo={}, amount={}, channel={}",
            event.getOrderNo(), event.getAmount(), event.getChannel());
    }

    private void handleRefundAccounting(RefundSuccessEvent event) {
        log.info("[记账] 退款成功记账 refundNo={}, orderNo={}, refundAmount={}",
            event.getRefundNo(), event.getOrderNo(), event.getRefundAmount());
    }
}
