package com.joker.spzx.manager.service.expense;

import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.entity.expense.ExpenseTagRule;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ExpenseTagRuleMatcherTest {

    private static ExpenseTagRule rule(String field, String type, String keyword) {
        ExpenseTagRule rule = new ExpenseTagRule();
        rule.setMatchField(field);
        rule.setMatchType(type);
        rule.setKeyword(keyword);
        return rule;
    }

    private static ExpenseOrder bill(String counterparty, String title, String remark, String channel) {
        ExpenseOrder bill = new ExpenseOrder();
        bill.setCounterparty(counterparty);
        bill.setTitle(title);
        bill.setRemark(remark);
        bill.setChannel(channel);
        return bill;
    }

    @Test
    void 分类全等命中() {
        assertTrue(ExpenseTagRuleMatcher.matches(
                rule("counterparty", "eq", "餐饮美食"), bill("餐饮美食", "外卖订单", null, "支付宝")));
    }

    @Test
    void 全等忽略首尾空格与大小写() {
        assertTrue(ExpenseTagRuleMatcher.matches(
                rule("counterparty", "eq", "  服饰装扮 "), bill("服饰装扮", null, null, null)));
        assertTrue(ExpenseTagRuleMatcher.matches(
                rule("channel", "eq", "ALIPAY"), bill(null, null, null, "alipay")));
    }

    @Test
    void 全等不做子串匹配() {
        assertFalse(ExpenseTagRuleMatcher.matches(
                rule("counterparty", "eq", "餐饮"), bill("餐饮美食", null, null, null)));
    }

    @Test
    void 包含匹配不区分大小写() {
        assertTrue(ExpenseTagRuleMatcher.matches(
                rule("title", "like", "万相台"), bill("商业服务", "万相台无界版扫码充值", null, null)));
        assertTrue(ExpenseTagRuleMatcher.matches(
                rule("title", "like", "deepseek"), bill(null, "DeepSeek-API服务", null, null)));
    }

    @Test
    void 比对字段为空时不命中() {
        assertFalse(ExpenseTagRuleMatcher.matches(
                rule("remark", "like", "退款"), bill("其他", "转账", null, "支付宝")));
    }

    @Test
    void 未知比对字段不命中而不是抛异常() {
        assertFalse(ExpenseTagRuleMatcher.matches(
                rule("amount", "eq", "10"), bill("其他", null, null, null)));
    }

    @Test
    void 关键词空白时不命中() {
        assertFalse(ExpenseTagRuleMatcher.matches(rule("counterparty", "eq", "   "), bill("其他", null, null, null)));
    }

    @Test
    void 金额区间是闭区间() {
        ExpenseTagRule rule = rule("counterparty", "eq", "转账红包");
        rule.setMinAmount(new BigDecimal("100"));
        rule.setMaxAmount(new BigDecimal("500"));

        ExpenseOrder at100 = bill("转账红包", null, null, null);
        at100.setAmount(new BigDecimal("100.00"));
        assertTrue(ExpenseTagRuleMatcher.matches(rule, at100));

        ExpenseOrder at99 = bill("转账红包", null, null, null);
        at99.setAmount(new BigDecimal("99.99"));
        assertFalse(ExpenseTagRuleMatcher.matches(rule, at99));

        ExpenseOrder at500 = bill("转账红包", null, null, null);
        at500.setAmount(new BigDecimal("500.00"));
        assertTrue(ExpenseTagRuleMatcher.matches(rule, at500));

        ExpenseOrder at501 = bill("转账红包", null, null, null);
        at501.setAmount(new BigDecimal("500.01"));
        assertFalse(ExpenseTagRuleMatcher.matches(rule, at501));
    }

    @Test
    void 金额字段为null按0参与区间判断() {
        ExpenseTagRule zeroMin = rule("counterparty", "eq", "其他");
        zeroMin.setMinAmount(BigDecimal.ZERO);
        assertTrue(ExpenseTagRuleMatcher.matches(zeroMin, bill("其他", null, null, null)));

        ExpenseTagRule oneMin = rule("counterparty", "eq", "其他");
        oneMin.setMinAmount(new BigDecimal("0.01"));
        assertFalse(ExpenseTagRuleMatcher.matches(oneMin, bill("其他", null, null, null)));
    }

    @Test
    void 入参为空返回false() {
        assertFalse(ExpenseTagRuleMatcher.matches(null, bill("其他", null, null, null)));
        assertFalse(ExpenseTagRuleMatcher.matches(rule("counterparty", "eq", "其他"), null));
    }
}
