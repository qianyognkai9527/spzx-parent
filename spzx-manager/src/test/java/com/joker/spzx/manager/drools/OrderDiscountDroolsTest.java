package com.joker.spzx.manager.drools;

import com.joker.spzx.manager.drools.model.OrderDiscountFact;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.kie.api.KieServices;
import org.kie.api.runtime.KieContainer;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

public class OrderDiscountDroolsTest {

    private DroolsRuleService droolsRuleService;

    @BeforeEach
    void setUp() throws Exception {
        KieServices kieServices = KieServices.Factory.get();
        KieContainer kieContainer = kieServices.getKieClasspathContainer();
        droolsRuleService = new DroolsRuleService(kieContainer);
    }

    @Test
    void vipOrderShouldGetTwentyPercentOff() {
        OrderDiscountFact fact = buildFact("VIP", "150");
        droolsRuleService.fireRules(fact);
        System.out.println(fact.toString());
        assertNotNull(fact.getPayableAmount());
        assertEquals(0, new BigDecimal("120").compareTo(fact.getPayableAmount()));
    }

    @Test
    void normalMemberLargeOrderShouldGetFivePercentOff() {
        OrderDiscountFact fact = buildFact("NORMAL", "300");
        droolsRuleService.fireRules(fact);
         System.out.println(fact.toString());
        assertNotNull(fact.getPayableAmount());
        assertEquals(0, new BigDecimal("285").compareTo(fact.getPayableAmount()));
    }

    @Test
    void orderWithoutDiscountRuleShouldKeepOriginalPrice() {
        OrderDiscountFact fact = buildFact("NORMAL", "50");
        droolsRuleService.fireRules(fact);
        assertNotNull(fact.getPayableAmount());
        assertEquals(0, new BigDecimal("50").compareTo(fact.getPayableAmount()));
    }

    private static OrderDiscountFact buildFact(String memberLevel, String amount) {
        OrderDiscountFact fact = new OrderDiscountFact();
        fact.setMemberLevel(memberLevel);
        fact.setOrderAmount(new BigDecimal(amount));
        fact.preprocess();
        return fact;
    }
}
