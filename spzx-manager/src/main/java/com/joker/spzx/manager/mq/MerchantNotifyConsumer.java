package com.joker.spzx.manager.mq;

import com.alibaba.fastjson.JSON;
import com.joker.spzx.manager.service.IdempotentService;
import com.joker.spzx.model.event.pay.PaySuccessEvent;
import com.joker.spzx.model.event.pay.RefundSuccessEvent;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.time.Duration;

@Slf4j
@Component
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
@RocketMQMessageListener(
    topic = PayEventProducer.TOPIC_NOTIFY,
    consumerGroup = "merchant_notify_group",
    selectorExpression = PayEventProducer.TAG_NOTIFY_PAY + " || " + PayEventProducer.TAG_NOTIFY_REFUND
)
public class MerchantNotifyConsumer implements RocketMQListener<org.apache.rocketmq.spring.support.RocketMQHeaders> {

    @Autowired
    private IdempotentService idempotentService;
    @Autowired
    private OkHttpClient okHttpClient;

    private static final Duration IDEMPOTENT_TTL = Duration.ofDays(7);

    @Override
    public void onMessage(org.apache.rocketmq.spring.support.RocketMQHeaders message) {
    }

    public void handlePayNotify(PaySuccessEvent event) {
        String idempotentKey = "mq:notify:pay:" + event.getOrderNo();
        if (!idempotentService.acquire(idempotentKey, IDEMPOTENT_TTL)) {
            log.info("商户通知幂等跳过 orderNo={}", event.getOrderNo());
            return;
        }
        sendNotify(event.getMerchantId() != null ? event.getMerchantId().toString() : "",
            "pay", event.getOrderNo(), JSON.toJSONString(event));
    }

    public void handleRefundNotify(RefundSuccessEvent event) {
        String idempotentKey = "mq:notify:refund:" + event.getRefundNo();
        if (!idempotentService.acquire(idempotentKey, IDEMPOTENT_TTL)) {
            log.info("商户退款通知幂等跳过 refundNo={}", event.getRefundNo());
            return;
        }
        sendNotify(event.getMerchantId() != null ? event.getMerchantId().toString() : "",
            "refund", event.getRefundNo(), JSON.toJSONString(event));
    }

    private void sendNotify(String merchantId, String type, String orderNo, String jsonBody) {
        try {
            String notifyUrl = "http://localhost:8080/notify/" + type;
            RequestBody body = RequestBody.create(jsonBody, MediaType.parse("application/json; charset=utf-8"));
            Request request = new Request.Builder()
                .url(notifyUrl)
                .post(body)
                .header("X-Merchant-Id", merchantId)
                .build();
            try (Response response = okHttpClient.newCall(request).execute()) {
                if (response.isSuccessful()) {
                    log.info("商户通知成功 type={}, orderNo={}, code={}", type, orderNo, response.code());
                } else {
                    log.warn("商户通知失败 type={}, orderNo={}, code={}", type, orderNo, response.code());
                }
            }
        } catch (Exception e) {
            log.error("商户通知异常 type={}, orderNo={}", type, orderNo, e);
        }
    }
}
