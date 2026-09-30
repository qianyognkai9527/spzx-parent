package com.joker.spzx.manager.service.expense;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.mapper.ExpenseOrderMapper;
import com.joker.spzx.manager.mapper.ExpenseOrderTagMapper;
import com.joker.spzx.manager.mapper.ExpenseTagMapper;
import com.joker.spzx.manager.mapper.ExpenseTagRuleMapper;
import com.joker.spzx.model.entity.expense.ExpenseOrder;
import com.joker.spzx.model.entity.expense.ExpenseOrderTag;
import com.joker.spzx.model.entity.expense.ExpenseTag;
import com.joker.spzx.model.entity.expense.ExpenseTagRule;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 账单自动打标：把「支付宝已经分好的类」批量落成 expense_order_tag，
 * 让标签筛选与按标签统计真正有数据。
 *
 * 两条硬约束：
 * - 只新增关联，从不删除。人工打过/改过的标签不会被下一轮跑批抹掉，所以重复执行是安全的。
 * - 默认先预览再落库（dryRun）。1922 笔账单一次全量打标是笔改不动的账，必须先看命中数。
 */
@Service
public class ExpenseTagRuleService {

    private static final Set<String> FIELDS = Set.of("counterparty", "title", "remark", "channel");
    private static final Set<String> TYPES = Set.of("eq", "like");
    private static final int CHUNK = 500;

    @Autowired
    private ExpenseTagRuleMapper ruleMapper;

    @Autowired
    private ExpenseOrderMapper orderMapper;

    @Autowired
    private ExpenseOrderTagMapper orderTagMapper;

    @Autowired
    private ExpenseTagMapper tagMapper;

    @Autowired
    private ExpensePeriodService periodService;

    /** 单条规则的命中情况 */
    public static class RuleHit {
        public Long ruleId;
        public Long tagId;
        public String tagName;
        public String keyword;
        public int bills;
        public BigDecimal amount = BigDecimal.ZERO;
    }

    /** 没被任何规则命中的账单，按支付宝分类聚合，用于告诉用户"还差哪些规则" */
    public static class Uncovered {
        public String counterparty;
        public int bills;
        public BigDecimal amount = BigDecimal.ZERO;
    }

    /** 一轮自动打标的结果（dryRun 与实跑共用） */
    public static class AutoTagResult {
        public boolean dryRun;
        public boolean onlyUntagged;
        public int billsScanned;
        public int billsMatched;
        public int skippedClosed;
        public int linksCreated;
        public List<RuleHit> ruleHits = new ArrayList<>();
        public List<Uncovered> uncovered = new ArrayList<>();
    }

    public List<ExpenseTagRule> listAll() {
        return ruleMapper.selectAllWithTagName();
    }

    public ExpenseTagRule getById(Long id) {
        return ruleMapper.selectById(id);
    }

    public String validate(ExpenseTagRule rule) {
        if (rule == null) {
            return "参数为空";
        }
        if (rule.getTagId() == null) {
            return "必须选择要打上的标签";
        }
        ExpenseTag tag = tagMapper.selectById(rule.getTagId());
        if (tag == null) {
            return "标签不存在";
        }
        String field = norm(rule.getMatchField());
        if (!FIELDS.contains(field)) {
            return "比对字段只能是 " + String.join(" / ", FIELDS);
        }
        String type = norm(rule.getMatchType());
        if (!TYPES.contains(type)) {
            return "匹配方式只能是 eq / like";
        }
        if (rule.getKeyword() == null || rule.getKeyword().isBlank()) {
            return "关键词不能为空";
        }
        if (rule.getMinAmount() != null && rule.getMaxAmount() != null
                && rule.getMinAmount().compareTo(rule.getMaxAmount()) > 0) {
            return "金额下限不能大于上限";
        }
        rule.setMatchField(field);
        rule.setMatchType(type);
        rule.setKeyword(rule.getKeyword().trim());
        return null;
    }

    /** 同一 (标签, 字段, 方式, 关键词) 只留一条，重复添加会让命中数看起来翻倍 */
    public String conflict(ExpenseTagRule rule) {
        Long hit = ruleMapper.selectCount(new LambdaQueryWrapper<ExpenseTagRule>()
                .eq(ExpenseTagRule::getTagId, rule.getTagId())
                .eq(ExpenseTagRule::getMatchField, rule.getMatchField())
                .eq(ExpenseTagRule::getMatchType, rule.getMatchType())
                .eq(ExpenseTagRule::getKeyword, rule.getKeyword())
                .ne(rule.getId() != null, ExpenseTagRule::getId, rule.getId()));
        return hit != null && hit > 0 ? "这条规则已经存在了" : null;
    }

    @Transactional(rollbackFor = Exception.class)
    public void save(ExpenseTagRule rule) {
        rule.setId(null);
        if (rule.getStatus() == null) {
            rule.setStatus(1);
        }
        ruleMapper.insert(rule);
    }

    @Transactional(rollbackFor = Exception.class)
    public void update(ExpenseTagRule rule) {
        ruleMapper.updateById(rule);
    }

    public void delete(Long id) {
        ruleMapper.deleteById(id);
    }

    /**
     * 跑一轮规则。dryRun=true 只统计命中，不写任何行。
     *
     * @param onlyUntagged 只处理还没有任何标签的账单；已经人工打过的跳过，避免和人工判断打架
     */
    public AutoTagResult run(boolean dryRun, boolean onlyUntagged) {
        List<ExpenseTagRule> rules = ruleMapper.selectList(new LambdaQueryWrapper<ExpenseTagRule>()
                .eq(ExpenseTagRule::getStatus, 1));
        AutoTagResult result = new AutoTagResult();
        result.dryRun = dryRun;
        result.onlyUntagged = onlyUntagged;
        if (rules.isEmpty()) {
            return result;
        }

        Map<Long, RuleHit> hitsByRule = new LinkedHashMap<>();
        for (ExpenseTagRule rule : rules) {
            RuleHit hit = new RuleHit();
            hit.ruleId = rule.getId();
            hit.tagId = rule.getTagId();
            hit.keyword = rule.getKeyword();
            hitsByRule.put(rule.getId(), hit);
        }
        fillTagNames(rules, hitsByRule);

        List<ExpenseOrder> bills = loadBills(onlyUntagged);
        result.billsScanned = bills.size();

        Set<String> closed = periodService.closedPeriods();
        List<ExpenseOrderTag> links = new ArrayList<>();
        Map<String, Uncovered> gaps = new LinkedHashMap<>();
        for (ExpenseOrder bill : bills) {
            String period = ExpensePeriodService.monthOf(bill.getExpenseDate());
            if (period != null && closed.contains(period)) {
                result.skippedClosed++;
                continue;
            }
            boolean matched = false;
            for (ExpenseTagRule rule : rules) {
                if (!ExpenseTagRuleMatcher.matches(rule, bill)) {
                    continue;
                }
                matched = true;
                RuleHit hit = hitsByRule.get(rule.getId());
                hit.bills++;
                hit.amount = hit.amount.add(bill.getAmount() == null ? BigDecimal.ZERO : bill.getAmount());
                ExpenseOrderTag link = new ExpenseOrderTag();
                link.setOrderId(bill.getId());
                link.setTagId(rule.getTagId());
                links.add(link);
            }
            if (matched) {
                result.billsMatched++;
            } else {
                recordGap(gaps, bill);
            }
        }
        result.ruleHits = new ArrayList<>(hitsByRule.values());
        result.uncovered = new ArrayList<>(gaps.values());
        result.uncovered.sort((a, b) -> Integer.compare(b.bills, a.bills));

        if (!dryRun && !links.isEmpty()) {
            result.linksCreated = insertLinks(links);
        }
        return result;
    }

    private void recordGap(Map<String, Uncovered> gaps, ExpenseOrder bill) {
        String key = bill.getCounterparty() == null || bill.getCounterparty().isBlank()
                ? "未分类" : bill.getCounterparty().trim();
        Uncovered gap = gaps.computeIfAbsent(key, k -> {
            Uncovered u = new Uncovered();
            u.counterparty = k;
            return u;
        });
        gap.bills++;
        gap.amount = gap.amount.add(bill.getAmount() == null ? BigDecimal.ZERO : bill.getAmount());
    }

    /** INSERT IGNORE 分块写：联合主键重复静默跳过，所以重复执行只影响 0 行 */    private int insertLinks(List<ExpenseOrderTag> links) {
        int created = 0;
        for (int from = 0; from < links.size(); from += CHUNK) {
            List<ExpenseOrderTag> part = links.subList(from, Math.min(links.size(), from + CHUNK));
            created += orderTagMapper.insertIgnoreBatch(new ArrayList<>(part));
        }
        return created;
    }

    private List<ExpenseOrder> loadBills(boolean onlyUntagged) {
        LambdaQueryWrapper<ExpenseOrder> qw = new LambdaQueryWrapper<ExpenseOrder>()
                .select(ExpenseOrder::getId, ExpenseOrder::getExpenseDate, ExpenseOrder::getAmount,
                        ExpenseOrder::getChannel, ExpenseOrder::getTitle,
                        ExpenseOrder::getCounterparty, ExpenseOrder::getRemark);
        if (onlyUntagged) {
            qw.apply("NOT EXISTS (SELECT 1 FROM expense_order_tag ot WHERE ot.order_id = expense_order.id)");
        }
        return orderMapper.selectList(qw);
    }

    private void fillTagNames(List<ExpenseTagRule> rules, Map<Long, RuleHit> hitsByRule) {
        Set<Long> tagIds = new HashSet<>(rules.stream().map(ExpenseTagRule::getTagId).toList());
        Map<Long, String> nameById = new HashMap<>();
        for (ExpenseTag tag : tagMapper.selectBatchIds(tagIds)) {
            nameById.put(tag.getId(), tag.getName());
        }
        hitsByRule.values().forEach(hit -> hit.tagName = nameById.get(hit.tagId));
    }

    private static String norm(String s) {
        return s == null ? "" : s.trim().toLowerCase();
    }
}
