package com.joker.spzx.manager.service.promo;

import com.joker.spzx.model.entity.promo.PromoPlan;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * 推广计划主档的纯校验规则（不碰库的那半截）。
 * 库里那两截（平台在不在注册表、店铺属不属于该平台）留给集成时验，
 * 本仓库的单测一律不拉 Spring 上下文。
 */
class PromoPlanCheckTest {

    private static PromoPlan row() {
        PromoPlan plan = new PromoPlan();
        plan.setPlatformCode(1);
        plan.setShopId(0L);
        plan.setCampaignId("83392769388");
        plan.setCampaignName("标准计划B");
        plan.setPlanType("keyword");
        plan.setBidType("custom_bid");
        return plan;
    }

    @Test
    void 采集登记的那四行原样能通过() {
        assertNull(PromoPlanService.checkFields(row()));
    }

    @Test
    void 归一化首字母大小写和空格() {
        PromoPlan plan = row();
        plan.setPlanType("  KEYWORD  ");
        plan.setBidType("ROI_Control");
        plan.setCampaignName("  秋冬款标准1 ");
        plan.setSource("  ");

        assertNull(PromoPlanService.checkFields(plan));
        assertEquals("keyword", plan.getPlanType());
        assertEquals("roi_control", plan.getBidType());
        assertEquals("秋冬款标准1", plan.getCampaignName());
        assertEquals("manual", plan.getSource());
    }

    @Test
    void 没填店铺落到零而不是空() {
        PromoPlan plan = row();
        plan.setShopId(null);

        assertNull(PromoPlanService.checkFields(plan));
        assertEquals(0L, plan.getShopId());
    }

    @Test
    void 出价方式给了新值只限长度不拦枚举() {
        PromoPlan plan = row();
        plan.setBidType("max_conversion");
        assertNull(PromoPlanService.checkFields(plan));

        PromoPlan tooLong = row();
        tooLong.setBidType("b".repeat(25));
        assertEquals("出价方式最长 24 个字符", PromoPlanService.checkFields(tooLong));
    }

    @Test
    void 出价基准填零没有意义而预算填零是不限() {
        PromoPlan zeroBid = row();
        zeroBid.setBidPrice(BigDecimal.ZERO);
        assertEquals("出价基准必须大于 0", PromoPlanService.checkFields(zeroBid));

        PromoPlan zeroBudget = row();
        zeroBudget.setDailyBudget(BigDecimal.ZERO);
        assertNull(PromoPlanService.checkFields(zeroBudget));
    }

    @Test
    void 负数和超出列宽的都挡在写库之前() {
        PromoPlan negative = row();
        negative.setDailyBudget(new BigDecimal("-1"));
        assertEquals("日预算不能为负数", PromoPlanService.checkFields(negative));

        PromoPlan tooBig = row();
        tooBig.setDailyBudget(new BigDecimal("100000000"));
        assertEquals("日预算最大 99999999.99 元", PromoPlanService.checkFields(tooBig));

        PromoPlan fits = row();
        fits.setDailyBudget(new BigDecimal("99999999.99"));
        assertNull(PromoPlanService.checkFields(fits));
    }

    @Test
    void 人群溢价按百分数收() {
        PromoPlan plan = row();
        plan.setPremiumPercent(30);
        assertNull(PromoPlanService.checkFields(plan));

        PromoPlan over = row();
        over.setPremiumPercent(1200);
        assertEquals("人群溢价应在 0-1000（百分数）之间，+30% 填 30", PromoPlanService.checkFields(over));
    }

    @Test
    void 投放状态留空是未确认而不是在投() {
        PromoPlan unset = row();
        unset.setOnlineStatus(null);
        assertNull(PromoPlanService.checkFields(unset));

        PromoPlan weird = row();
        weird.setOnlineStatus(2);
        assertEquals("投放状态只有 在投/停投/未确认 三种", PromoPlanService.checkFields(weird));
    }

    @Test
    void 起止日期不能反() {
        PromoPlan plan = row();
        plan.setStartDate(LocalDate.of(2026, 10, 8));
        plan.setEndDate(LocalDate.of(2026, 10, 1));
        assertEquals("开始日期不能晚于结束日期", PromoPlanService.checkFields(plan));

        PromoPlan same = row();
        same.setStartDate(LocalDate.of(2026, 10, 8));
        same.setEndDate(LocalDate.of(2026, 10, 8));
        assertNull(PromoPlanService.checkFields(same));
    }

    @Test
    void 计划id是自然键不许空() {
        PromoPlan blank = row();
        blank.setCampaignId("   ");
        assertEquals("计划 id 不能为空，它要和采集回来的花费数据对得上", PromoPlanService.checkFields(blank));

        PromoPlan longId = row();
        longId.setCampaignId("9".repeat(65));
        assertEquals("计划 id 最长 64 个字符", PromoPlanService.checkFields(longId));
    }

    @Test
    void 类型不在花费表那套枚举里就拒绝() {
        PromoPlan plan = row();
        plan.setPlanType("live");
        assertEquals("计划类型只能是 keyword / crowd / site / other",
                PromoPlanService.checkFields(plan));
    }

    @Test
    void 文本列按列宽收口() {
        PromoPlan plan = row();
        plan.setCampaignName("名".repeat(256));
        assertEquals("计划名称最长 255 个字符", PromoPlanService.checkFields(plan));

        PromoPlan remark = row();
        remark.setRemark("x".repeat(501));
        assertEquals("备注最长 500 个字符", PromoPlanService.checkFields(remark));

        PromoPlan owner = row();
        owner.setOwner("a".repeat(33));
        assertEquals("负责人最长 32 个字符", PromoPlanService.checkFields(owner));
    }
}
