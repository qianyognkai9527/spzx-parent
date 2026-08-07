package com.joker.spzx.manager.mq;

import com.alibaba.fastjson.JSON;
import com.joker.spzx.model.event.pay.PaySuccessEvent;
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
    consumerGroup = "reconcile_prep_group",
    selectorExpression = PayEventProducer.TAG_PAY_SUCCESS
)
public class ReconcilePrepConsumer implements RocketMQListener<String> {

    @Override
    public void onMessage(String message) {
        try {
            PaySuccessEvent event = JSON.parseObject(message, PaySuccessEvent.class);
            log.info("[对账预备] 写入对账预备表 orderNo={}, outTradeNo={}, amount={}, channel={}",
                event.getOrderNo(), event.getOutTradeNo(), event.getAmount(), event.getChannel());
        } catch (Exception e) {
            log.error("对账预备消费失败 message={}", message, e);
        }
    }
}
