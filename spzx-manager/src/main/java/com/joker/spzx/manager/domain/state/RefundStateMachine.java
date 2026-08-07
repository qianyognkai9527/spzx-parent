package com.joker.spzx.manager.domain.state;

import com.joker.spzx.model.enums.pay.RefundStatusEnum;
import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Set;

@Component
public class RefundStateMachine {

    private static final Map<RefundStatusEnum, Set<RefundStatusEnum>> TRANSITIONS = Map.of(
        RefundStatusEnum.REFUND_PENDING,    Set.of(RefundStatusEnum.REFUND_PROCESSING, RefundStatusEnum.REFUND_FAILED),
        RefundStatusEnum.REFUND_PROCESSING, Set.of(RefundStatusEnum.REFUND_SUCCESS, RefundStatusEnum.REFUND_FAILED),
        RefundStatusEnum.REFUND_SUCCESS,    Set.of(),
        RefundStatusEnum.REFUND_FAILED,     Set.of(RefundStatusEnum.REFUND_PENDING)
    );

    public void checkTransition(RefundStatusEnum from, RefundStatusEnum to) {
        Set<RefundStatusEnum> allowed = TRANSITIONS.getOrDefault(from, Set.of());
        if (!allowed.contains(to)) {
            throw new PayException(PayErrorCode.ORDER_STATUS_INVALID,
                from.getDesc() + " → " + to.getDesc());
        }
    }

    public boolean canTransition(RefundStatusEnum from, RefundStatusEnum to) {
        return TRANSITIONS.getOrDefault(from, Set.of()).contains(to);
    }
}
