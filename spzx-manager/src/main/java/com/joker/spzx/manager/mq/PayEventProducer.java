package com.joker.spzx.manager.mq;

import com.alibaba.fastjson.JSON;
import com.joker.spzx.model.event.pay.*;
import lombok.extern.slf4j.Slf4j;
import org.apache.rocketmq.client.producer.SendResult;
import org.apache.rocketmq.client.producer.TransactionSendResult;
import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.Message;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class PayEventProducer {

    public static final String TOPIC_PAY = "pay_topic";
    public static final String TOPIC_NOTIFY = "pay_notify_topic";

    public static final String TAG_PAY_CREATED = "pay.created";
    public static final String TAG_PAY_SUCCESS = "pay.success";
    public static final String TAG_PAY_FAILED = "pay.failed";
    public static final String TAG_PAY_CLOSED = "pay.closed";
    public static final String TAG_REFUND_REQUESTED = "refund.requested";
    public static final String TAG_REFUND_SUCCESS = "refund.success";
    public static final String TAG_NOTIFY_PAY = "notify.pay";
    public static final String TAG_NOTIFY_REFUND = "notify.refund";

    @Autowired(required = false)
    private RocketMQTemplate rocketMQTemplate;

    private boolean mqDisabled() {
        return rocketMQTemplate == null;
    }

    public void sendPayCreated(PayCreatedEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 pay.created orderNo={}", event.getOrderNo()); return; }
        String destination = TOPIC_PAY + ":" + TAG_PAY_CREATED;
        Message<PayCreatedEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getOrderNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 pay.created orderNo={}, msgId={}", event.getOrderNo(), result.getMsgId());
    }

    public void sendPaySuccess(PaySuccessEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 pay.success orderNo={}", event.getOrderNo()); return; }
        String destination = TOPIC_PAY + ":" + TAG_PAY_SUCCESS;
        Message<PaySuccessEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getOrderNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 pay.success orderNo={}, msgId={}", event.getOrderNo(), result.getMsgId());
    }

    public void sendPayFailed(PayFailedEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 pay.failed orderNo={}", event.getOrderNo()); return; }
        String destination = TOPIC_PAY + ":" + TAG_PAY_FAILED;
        Message<PayFailedEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getOrderNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 pay.failed orderNo={}, msgId={}", event.getOrderNo(), result.getMsgId());
    }

    public void sendPayClosed(PayClosedEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 pay.closed orderNo={}", event.getOrderNo()); return; }
        String destination = TOPIC_PAY + ":" + TAG_PAY_CLOSED;
        Message<PayClosedEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getOrderNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 pay.closed orderNo={}, msgId={}", event.getOrderNo(), result.getMsgId());
    }

    public void sendRefundRequested(RefundRequestedEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 refund.requested refundNo={}", event.getRefundNo()); return; }
        String destination = TOPIC_PAY + ":" + TAG_REFUND_REQUESTED;
        Message<RefundRequestedEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getRefundNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 refund.requested refundNo={}, msgId={}", event.getRefundNo(), result.getMsgId());
    }

    public void sendRefundSuccess(RefundSuccessEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 refund.success refundNo={}", event.getRefundNo()); return; }
        String destination = TOPIC_PAY + ":" + TAG_REFUND_SUCCESS;
        Message<RefundSuccessEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getRefundNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 refund.success refundNo={}, msgId={}", event.getRefundNo(), result.getMsgId());
    }

    public void sendMerchantPayNotify(PaySuccessEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 notify.pay orderNo={}", event.getOrderNo()); return; }
        String destination = TOPIC_NOTIFY + ":" + TAG_NOTIFY_PAY;
        Message<PaySuccessEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getOrderNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 notify.pay orderNo={}, msgId={}", event.getOrderNo(), result.getMsgId());
    }

    public void sendMerchantRefundNotify(RefundSuccessEvent event) {
        if (mqDisabled()) { log.info("[MQ未启用] 跳过 notify.refund refundNo={}", event.getRefundNo()); return; }
        String destination = TOPIC_NOTIFY + ":" + TAG_NOTIFY_REFUND;
        Message<RefundSuccessEvent> message = MessageBuilder.withPayload(event)
            .setHeader("KEYS", event.getRefundNo()).build();
        SendResult result = rocketMQTemplate.syncSend(destination, message);
        log.info("发送 notify.refund refundNo={}, msgId={}", event.getRefundNo(), result.getMsgId());
    }
}
