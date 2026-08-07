package com.joker.spzx.manager.mq;

import com.alibaba.fastjson.JSON;
import com.joker.spzx.model.event.pay.PayCreatedEvent;
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
    consumerGroup = "risk_control_group",
    selectorExpression = PayEventProducer.TAG_PAY_CREATED + " || " + PayEventProducer.TAG_PAY_SUCCESS
)
public class RiskControlConsumer implements RocketMQListener<String> {

    @Override
    public void onMessage(String message) {
        try {
            if (message.contains("payTime")) {
                PaySuccessEvent event = JSON.parseObject(message, PaySuccessEvent.class);
                handlePostRisk(event);
            } else {
                PayCreatedEvent event = JSON.parseObject(message, PayCreatedEvent.class);
                handleInRisk(event);
            }
        } catch (Exception e) {
            log.error("风控消费失败 message={}", message, e);
        }
    }

    private void handleInRisk(PayCreatedEvent event) {
        log.info("[风控-事中] 订单创建风控检查 orderNo={}, amount={}, channel={}",
            event.getOrderNo(), event.getAmount(), event.getChannel());
    }

    private void handlePostRisk(PaySuccessEvent event) {
        log.info("[风控-事后] 支付成功风控分析 orderNo={}, amount={}, channel={}",
            event.getOrderNo(), event.getAmount(), event.getChannel());
    }
}
