package com.joker.spzx.manager.facade;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.manager.domain.state.PaymentStateMachine;
import com.joker.spzx.manager.mapper.PaymentInfoMapper;
import com.joker.spzx.manager.mq.PayEventProducer;
import com.joker.spzx.manager.pay.strategy.PayStrategy;
import com.joker.spzx.manager.pay.strategy.PayStrategyFactory;
import com.joker.spzx.manager.service.DistributedLockService;
import com.joker.spzx.manager.service.IdempotentService;
import com.joker.spzx.model.dto.pay.PayCreateDTO;
import com.joker.spzx.model.dto.pay.RefundCreateDTO;
import com.joker.spzx.model.entity.pay.PaymentInfo;
import com.joker.spzx.model.enums.pay.ChannelEnum;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import com.joker.spzx.model.enums.pay.PaymentStatusEnum;
import com.joker.spzx.model.enums.pay.PayTypeEnum;
import com.joker.spzx.model.event.pay.*;
import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.vo.pay.PayCreateVO;
import com.joker.spzx.model.vo.pay.PayNotifyResult;
import com.joker.spzx.model.vo.pay.PayQueryVO;
import com.joker.spzx.model.vo.pay.RefundNotifyResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.LocalDateTime;

@Slf4j
@Service
public class PaymentFacade {

    private static final Duration IDEMPOTENT_TTL = Duration.ofHours(24);
    private static final Duration NOTIFY_IDEMPOTENT_TTL = Duration.ofDays(7);
    private static final Duration LOCK_WAIT = Duration.ofSeconds(3);
    private static final Duration LOCK_LEASE = Duration.ofSeconds(30);

    @Autowired
    private PayStrategyFactory strategyFactory;
    @Autowired
    private PaymentInfoMapper paymentInfoMapper;
    @Autowired
    private IdempotentService idempotentService;
    @Autowired
    private DistributedLockService lockService;
    @Autowired
    private PaymentStateMachine stateMachine;
    @Autowired
    private PayEventProducer eventProducer;

    @Transactional(rollbackFor = Exception.class)
    public PayCreateVO createPayment(PayCreateDTO dto) {
        String idempotentKey = "pay:idempotent:" + dto.getOrderNo();
        String lockKey = "pay:lock:" + dto.getOrderNo();

        if (!idempotentService.acquire(idempotentKey, IDEMPOTENT_TTL)) {
            throw new PayException(PayErrorCode.ORDER_EXISTS);
        }

        return lockService.executeWithLock(lockKey, LOCK_WAIT, LOCK_LEASE, () -> {
            PaymentInfo existing = findByOrderNo(dto.getOrderNo());
            if (existing != null) {
                if (existing.getPaymentStatus() != null
                        && existing.getPaymentStatus() == PaymentStatusEnum.PAYING.getCode()) {
                    throw new PayException(PayErrorCode.ORDER_PROCESSING);
                }
                stateMachine.checkTransition(
                    PaymentStatusEnum.fromCode(existing.getPaymentStatus()),
                    PaymentStatusEnum.PAYING);
            }

            PayStrategy strategy = strategyFactory.getStrategy(dto.getPayType());
            PayCreateVO vo = strategy.createPayment(dto);
            savePaymentInfo(dto, vo);

            String channel = ChannelEnum.fromPayType(PayTypeEnum.fromCode(dto.getPayType())).getCode();
            eventProducer.sendPayCreated(PayCreatedEvent.of(
                dto.getOrderNo(), vo.getPrepayId() != null ? vo.getPrepayId() : vo.getTradeNo(),
                dto.getPayType(), channel, dto.getAmount(), dto.getSubject()));
            return vo;
        });
    }

    @Transactional(rollbackFor = Exception.class)
    public PayNotifyResult handleNotify(PayNotifyResult result, String channel) {
        if (!result.isSuccess()) {
            return result;
        }

        String idempotentKey = "pay:notify:" + channel + ":" + result.getOutTradeNo();
        if (!idempotentService.acquire(idempotentKey, NOTIFY_IDEMPOTENT_TTL)) {
            log.info("回调幂等拦截 orderNo={}, outTradeNo={}", result.getOrderNo(), result.getOutTradeNo());
            return result;
        }

        String lockKey = "pay:notify:lock:" + result.getOrderNo();
        lockService.executeWithLock(lockKey, LOCK_WAIT, LOCK_LEASE, () -> {
            updatePaymentOnSuccess(result);
        });

        PaySuccessEvent successEvent = PaySuccessEvent.of(
            result.getOrderNo(), result.getOutTradeNo(),
            result.getPayType(), channel, result.getAmount(), result.getRawBody());
        eventProducer.sendPaySuccess(successEvent);
        eventProducer.sendMerchantPayNotify(successEvent);
        return result;
    }

    @Transactional(rollbackFor = Exception.class)
    public RefundNotifyResult handleRefundNotify(RefundNotifyResult result, String channel) {
        if (!result.isSuccess()) {
            return result;
        }

        String idempotentKey = "pay:refund:notify:" + channel + ":" + result.getRefundNo();
        if (!idempotentService.acquire(idempotentKey, NOTIFY_IDEMPOTENT_TTL)) {
            log.info("退款回调幂等拦截 orderNo={}, refundNo={}", result.getOrderNo(), result.getRefundNo());
            return result;
        }

        String lockKey = "pay:refund:notify:lock:" + result.getOrderNo();
        lockService.executeWithLock(lockKey, LOCK_WAIT, LOCK_LEASE, () -> {
            updatePaymentOnRefundSuccess(result);
        });

        RefundSuccessEvent successEvent = RefundSuccessEvent.of(
            result.getRefundNo(), result.getOrderNo(),
            channel, result.getRefundAmount(), result.getRawBody());
        eventProducer.sendRefundSuccess(successEvent);
        eventProducer.sendMerchantRefundNotify(successEvent);
        return result;
    }

    @Transactional(rollbackFor = Exception.class)
    public void refund(RefundCreateDTO dto) {
        String idempotentKey = "pay:refund:" + dto.getRefundNo();
        String lockKey = "pay:lock:" + dto.getOrderNo();

        if (!idempotentService.acquire(idempotentKey, IDEMPOTENT_TTL)) {
            throw new PayException(PayErrorCode.REFUND_DUPLICATE);
        }

        lockService.executeWithLock(lockKey, LOCK_WAIT, LOCK_LEASE, () -> {
            PaymentInfo existing = findByOrderNo(dto.getOrderNo());
            if (existing == null) {
                throw new PayException(PayErrorCode.ORDER_NOT_FOUND);
            }
            if (existing.getPaymentStatus() == null
                    || existing.getPaymentStatus() != PaymentStatusEnum.PAID.getCode()) {
                throw new PayException(PayErrorCode.REFUND_ORDER_NOT_PAID);
            }
            stateMachine.checkTransition(
                PaymentStatusEnum.fromCode(existing.getPaymentStatus()),
                PaymentStatusEnum.REFUNDING);

            PayStrategy strategy = strategyFactory.getStrategy(dto.getPayType());
            strategy.refund(dto);
            paymentInfoMapper.update(null,
                new LambdaUpdateWrapper<PaymentInfo>()
                    .eq(PaymentInfo::getOrderNo, dto.getOrderNo())
                    .set(PaymentInfo::getPaymentStatus, PaymentStatusEnum.REFUNDING.getCode()));

            String channel = ChannelEnum.fromPayType(PayTypeEnum.fromCode(dto.getPayType())).getCode();
            eventProducer.sendRefundRequested(RefundRequestedEvent.of(
                dto.getRefundNo(), dto.getOrderNo(), channel,
                dto.getRefundAmount(), dto.getTotalAmount(), dto.getReason()));
        });
    }

    public PayQueryVO queryPayment(String orderNo, Integer payType) {
        PayStrategy strategy = strategyFactory.getStrategy(payType);
        return strategy.queryPayment(orderNo);
    }

    @Transactional(rollbackFor = Exception.class)
    public void closePayment(String orderNo, Integer payType) {
        String lockKey = "pay:lock:" + orderNo;
        lockService.executeWithLock(lockKey, LOCK_WAIT, LOCK_LEASE, () -> {
            PaymentInfo existing = findByOrderNo(orderNo);
            if (existing == null) {
                throw new PayException(PayErrorCode.ORDER_NOT_FOUND);
            }
            stateMachine.checkTransition(
                PaymentStatusEnum.fromCode(existing.getPaymentStatus()),
                PaymentStatusEnum.CLOSED);

            PayStrategy strategy = strategyFactory.getStrategy(payType);
            strategy.closePayment(orderNo);
            paymentInfoMapper.update(null,
                new LambdaUpdateWrapper<PaymentInfo>()
                    .eq(PaymentInfo::getOrderNo, orderNo)
                    .set(PaymentInfo::getPaymentStatus, PaymentStatusEnum.CLOSED.getCode()));

            String channel = ChannelEnum.fromPayType(PayTypeEnum.fromCode(payType)).getCode();
            eventProducer.sendPayClosed(PayClosedEvent.of(orderNo, channel));
        });
    }

    public PayTypeEnum resolvePayType(String orderNo) {
        PaymentInfo info = findByOrderNo(orderNo);
        if (info != null && info.getPayType() != null) {
            return PayTypeEnum.fromCode(info.getPayType());
        }
        return null;
    }

    private void savePaymentInfo(PayCreateDTO dto, PayCreateVO vo) {
        PaymentInfo info = new PaymentInfo();
        info.setOrderNo(dto.getOrderNo());
        info.setPayType(dto.getPayType());
        info.setAmount(dto.getAmount());
        info.setContent(dto.getSubject());
        info.setPaymentStatus(PaymentStatusEnum.PAYING.getCode());
        if (vo.getPrepayId() != null) {
            info.setOutTradeNo(vo.getPrepayId());
        } else if (vo.getTradeNo() != null) {
            info.setOutTradeNo(vo.getTradeNo());
        }
        paymentInfoMapper.insert(info);
    }

    private void updatePaymentOnSuccess(PayNotifyResult result) {
        PaymentInfo existing = findByOrderNo(result.getOrderNo());
        if (existing == null) {
            log.warn("回调成功但订单不存在 orderNo={}", result.getOrderNo());
            return;
        }
        if (existing.getPaymentStatus() != null
                && existing.getPaymentStatus() == PaymentStatusEnum.PAID.getCode()) {
            log.info("订单已支付，幂等跳过 orderNo={}", result.getOrderNo());
            return;
        }
        stateMachine.checkTransition(
            PaymentStatusEnum.fromCode(existing.getPaymentStatus()),
            PaymentStatusEnum.PAID);
        paymentInfoMapper.update(null,
            new LambdaUpdateWrapper<PaymentInfo>()
                .eq(PaymentInfo::getOrderNo, result.getOrderNo())
                .set(PaymentInfo::getPaymentStatus, PaymentStatusEnum.PAID.getCode())
                .set(PaymentInfo::getOutTradeNo, result.getOutTradeNo())
                .set(PaymentInfo::getCallbackTime, LocalDateTime.now())
                .set(PaymentInfo::getCallbackContent, result.getRawBody()));
    }

    private void updatePaymentOnRefundSuccess(RefundNotifyResult result) {
        PaymentInfo existing = findByOrderNo(result.getOrderNo());
        if (existing == null) {
            log.warn("退款回调成功但订单不存在 orderNo={}", result.getOrderNo());
            return;
        }
        if (existing.getPaymentStatus() != null
                && existing.getPaymentStatus() == PaymentStatusEnum.REFUNDED.getCode()) {
            log.info("订单已退款，幂等跳过 orderNo={}", result.getOrderNo());
            return;
        }
        paymentInfoMapper.update(null,
            new LambdaUpdateWrapper<PaymentInfo>()
                .eq(PaymentInfo::getOrderNo, result.getOrderNo())
                .set(PaymentInfo::getPaymentStatus, PaymentStatusEnum.REFUNDED.getCode())
                .set(PaymentInfo::getCallbackTime, LocalDateTime.now())
                .set(PaymentInfo::getCallbackContent, result.getRawBody()));
    }

    private PaymentInfo findByOrderNo(String orderNo) {
        return paymentInfoMapper.selectOne(
            new LambdaQueryWrapper<PaymentInfo>()
                .eq(PaymentInfo::getOrderNo, orderNo));
    }
}
