package com.joker.spzx.manager.util;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** 视频生成计费：按 5 秒档单价线性折算，价格缺失/非法按 0（不计费不拦截） */
public final class VideoPricing {

    private static final BigDecimal BASE_SECONDS = BigDecimal.valueOf(5);
    public static final BigDecimal ZERO = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);

    private VideoPricing() {
    }

    public static BigDecimal parse(String raw) {
        if (raw == null || raw.isBlank()) return null;
        try {
            BigDecimal v = new BigDecimal(raw.trim());
            return v.signum() < 0 ? null : v;
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** est = 单价 × duration / 5，HALF_UP 保留 2 位；单价为 null → ZERO */
    public static BigDecimal estimate(BigDecimal perFiveSec, Integer durationSec) {
        if (perFiveSec == null || durationSec == null || durationSec <= 0) return ZERO;
        return perFiveSec.multiply(BigDecimal.valueOf(durationSec))
                .divide(BASE_SECONDS, 2, RoundingMode.HALF_UP);
    }
}
