package com.joker.spzx.manager.service.expense;

import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.entity.expense.ExpenseTagRule;

import java.math.BigDecimal;

/**
 * 规则匹配的纯函数部分：不碰数据库、不依赖 Spring，单测直接喂实体对象。
 *
 * 一条规则命中条件 = 字段比对通过 且 金额落在区间内。
 */
public final class ExpenseTagRuleMatcher {

    private ExpenseTagRuleMatcher() {
    }

    public static boolean matches(ExpenseTagRule rule, ExpenseOrder bill) {
        if (rule == null || bill == null) {
            return false;
        }
        if (!fieldMatches(rule, bill)) {
            return false;
        }
        return amountInRule(rule, bill.getAmount());
    }

    private static boolean fieldMatches(ExpenseTagRule rule, ExpenseOrder bill) {
        String actual = fieldValue(rule.getMatchField(), bill);
        String keyword = rule.getKeyword() == null ? "" : rule.getKeyword().trim();
        if (actual == null || actual.isBlank() || keyword.isEmpty()) {
            return false;
        }
        if ("like".equalsIgnoreCase(rule.getMatchType())) {
            return actual.toLowerCase().contains(keyword.toLowerCase());
        }
        return actual.trim().equalsIgnoreCase(keyword);
    }

    /**
     * 金额区间是闭区间；任一端为空表示该方向不限。
     * 账单金额为 null 时视为 0，这样「下限 0」这类规则不会因为历史脏数据漏判。
     */
    private static boolean amountInRule(ExpenseTagRule rule, BigDecimal amount) {
        if (rule.getMinAmount() == null && rule.getMaxAmount() == null) {
            return true;
        }
        BigDecimal value = amount == null ? BigDecimal.ZERO : amount;
        if (rule.getMinAmount() != null && value.compareTo(rule.getMinAmount()) < 0) {
            return false;
        }
        return rule.getMaxAmount() == null || value.compareTo(rule.getMaxAmount()) <= 0;
    }

    private static String fieldValue(String field, ExpenseOrder bill) {
        if (field == null) {
            return null;
        }
        return switch (field.toLowerCase()) {
            case "counterparty" -> bill.getCounterparty();
            case "title" -> bill.getTitle();
            case "remark" -> bill.getRemark();
            case "channel" -> bill.getChannel();
            default -> null;
        };
    }
}
