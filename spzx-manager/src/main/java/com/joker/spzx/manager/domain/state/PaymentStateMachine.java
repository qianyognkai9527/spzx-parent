package com.joker.spzx.manager.domain.state;

import com.joker.spzx.model.enums.pay.PaymentStatusEnum;
import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Set;

@Component
public class PaymentStateMachine {

    private static final Map<PaymentStatusEnum, Set<PaymentStatusEnum>> TRANSITIONS = Map.of(
        PaymentStatusEnum.UNPAID,          Set.of(PaymentStatusEnum.PAYING, PaymentStatusEnum.CLOSED),
        PaymentStatusEnum.PAYING,          Set.of(PaymentStatusEnum.PAID, PaymentStatusEnum.PAY_ERROR, PaymentStatusEnum.CLOSED),
        PaymentStatusEnum.PAID,            Set.of(PaymentStatusEnum.REFUNDING, PaymentStatusEnum.PARTIAL_REFUNDED),
        PaymentStatusEnum.PARTIAL_REFUNDED,Set.of(PaymentStatusEnum.REFUNDING, PaymentStatusEnum.REFUNDED, PaymentStatusEnum.PARTIAL_REFUNDED),
        PaymentStatusEnum.REFUNDING,       Set.of(PaymentStatusEnum.PAID, PaymentStatusEnum.PARTIAL_REFUNDED, PaymentStatusEnum.REFUNDED, PaymentStatusEnum.REFUND_FAILED),
        PaymentStatusEnum.REFUND_FAILED,   Set.of(PaymentStatusEnum.REFUNDING),
        PaymentStatusEnum.PAY_ERROR,       Set.of(PaymentStatusEnum.PAYING),
        PaymentStatusEnum.REFUNDED,        Set.of(),
        PaymentStatusEnum.CLOSED,          Set.of()
    );

    public void checkTransition(PaymentStatusEnum from, PaymentStatusEnum to) {
        Set<PaymentStatusEnum> allowed = TRANSITIONS.getOrDefault(from, Set.of());
        if (!allowed.contains(to)) {
            throw new PayException(PayErrorCode.ORDER_STATUS_INVALID,
                from.getDesc() + " → " + to.getDesc());
        }
    }

    public boolean canTransition(PaymentStatusEnum from, PaymentStatusEnum to) {
        return TRANSITIONS.getOrDefault(from, Set.of()).contains(to);
    }
}
