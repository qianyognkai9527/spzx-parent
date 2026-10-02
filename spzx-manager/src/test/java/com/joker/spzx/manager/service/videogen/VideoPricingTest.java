package com.joker.spzx.manager.service.videogen;

import com.joker.spzx.manager.util.VideoPricing;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class VideoPricingTest {

    @Test
    void estimate按5秒档线性折算() {
        assertEquals(new BigDecimal("7.67"), VideoPricing.estimate(new BigDecimal("7.67"), 5));
        assertEquals(new BigDecimal("15.34"), VideoPricing.estimate(new BigDecimal("7.67"), 10));
        assertEquals(new BigDecimal("2.50"), VideoPricing.estimate(new BigDecimal("1.25"), 10));
    }

    @Test
    void estimate缺失输入按零() {
        assertEquals(VideoPricing.ZERO, VideoPricing.estimate(null, 5));
        assertEquals(VideoPricing.ZERO, VideoPricing.estimate(new BigDecimal("7.67"), null));
        assertEquals(VideoPricing.ZERO, VideoPricing.estimate(new BigDecimal("7.67"), 0));
    }

    @Test
    void parse容错非法值() {
        assertEquals(new BigDecimal("7.67"), VideoPricing.parse(" 7.67 "));
        assertNull(VideoPricing.parse(null));
        assertNull(VideoPricing.parse(""));
        assertNull(VideoPricing.parse("abc"));
        assertNull(VideoPricing.parse("-1"));
    }
}
