package com.joker.spzx.manager.drools;

import lombok.RequiredArgsConstructor;
import org.kie.api.runtime.KieContainer;
import org.kie.api.runtime.KieSession;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.stereotype.Service;

import java.util.Collection;

@Service
@RequiredArgsConstructor
@ConditionalOnBean(KieContainer.class)
public class DroolsRuleService {

    private final KieContainer kieContainer;

    /**
     * 对单个事实对象执行全部匹配规则
     */
    public void fireRules(Object fact) {
        fireRules(fact, null);
    }

    /**
     * 对单个事实对象执行规则，可指定 agenda-group
     */
    public void fireRules(Object fact, String agendaGroup) {
        KieSession kieSession = kieContainer.newKieSession("ksession-rules");
        try {
            if (agendaGroup != null && !agendaGroup.isBlank()) {
                kieSession.getAgenda().getAgendaGroup(agendaGroup).setFocus();
            }
            kieSession.insert(fact);
            kieSession.fireAllRules();
        } finally {
            kieSession.dispose();
        }
    }

    /**
     * 对多个事实对象批量执行规则
     */
    public void fireRules(Collection<?> facts) {
        KieSession kieSession = kieContainer.newKieSession("ksession-rules");
        try {
            facts.forEach(kieSession::insert);
            kieSession.fireAllRules();
        } finally {
            kieSession.dispose();
        }
    }
}
