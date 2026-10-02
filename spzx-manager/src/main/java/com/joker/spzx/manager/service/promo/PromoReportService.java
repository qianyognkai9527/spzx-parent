package com.joker.spzx.manager.service.promo;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.mapper.PromoReportMapper;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.model.vo.promo.PromoDailyVo;
import com.joker.spzx.model.vo.promo.PromoItemVo;
import com.joker.spzx.model.vo.promo.PromoPlanVo;
import com.joker.spzx.model.vo.promo.PromoSummaryVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Set;

/**
 * 推广日报查询。只读：数据由 automation 侧的接口采集器写入，这里不产生任何事实行。
 *
 * 默认区间是「昨天往前 14 天」而不是「今天往前 14 天」—— 采集器只取昨天及更早
 * （万相台当天数据未结算），把今天放进区间只会让人以为"今天零花费"是真的零。
 */
@Service
public class PromoReportService {

    /** 宝贝维度的筛选项。非法值退回 all，不让前端一个拼错就整页空 */
    private static final Set<String> FACETS = Set.of("all", "noDeal", "orphan", "unpriced");
    private static final Set<String> SORTS = Set.of("charge", "gmv", "roi", "click");
    private static final Set<String> PLAN_TYPES = Set.of("all", "keyword", "crowd", "site", "other");

    /** 区间上限：采集器最多回补 90 天，再长必然出现"没采"和"没投"分不清的日子 */
    public static final int MAX_RANGE_DAYS = 90;
    public static final int DEFAULT_DAYS = 14;

    @Autowired
    private PromoReportMapper promoReportMapper;

    /** 纯函数：解析 yyyy-MM-dd，坏值返回 null 而不是抛异常 */
    public static LocalDate parseDate(String s) {
        if (s == null || s.isBlank()) {
            return null;
        }
        try {
            return LocalDate.parse(s.trim());
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    /**
     * 纯函数：把任意入参收敛成合法的 [from, to]。
     * 缺省取昨天往前 14 天；起止颠倒自动交换；超上限从 to 往前截，而不是报错——
     * 看板被一个手滑的日期搞成空白页比被截断更糟。
     */
    public static String[] normalizeRange(String from, String to, LocalDate today) {
        LocalDate t = parseDate(to);
        if (t == null) {
            t = today.minusDays(1);
        }
        LocalDate f = parseDate(from);
        if (f == null) {
            f = t.minusDays(DEFAULT_DAYS - 1);
        }
        if (f.isAfter(t)) {
            LocalDate swap = f;
            f = t;
            t = swap;
        }
        if (t.isAfter(today)) {
            t = today;
        }
        if (java.time.temporal.ChronoUnit.DAYS.between(f, t) + 1 > MAX_RANGE_DAYS) {
            f = t.minusDays(MAX_RANGE_DAYS - 1L);
        }
        return new String[]{f.toString(), t.toString()};
    }

    public static String normalizeChoice(String value, Set<String> allowed, String fallback) {
        if (value == null) {
            return fallback;
        }
        String v = value.trim();
        return allowed.contains(v) ? v : fallback;
    }

    public PromoSummaryVo summary(String from, String to, String planType) {
        String[] r = normalizeRange(from, to, LocalDate.now());
        PromoSummaryVo vo = promoReportMapper.selectSummary(r[0], r[1],
                normalizeChoice(planType, PLAN_TYPES, "all"));
        if (vo == null) {
            vo = new PromoSummaryVo();
            vo.setDays(0);
        }
        // dateFrom/dateTo 是「有报表的天」，请求区间另存一份：
        // 默认 14 天但只回 4 天时，不标出来就会被读成"花费掉了"而不是"中间那些天没数据"
        vo.setRangeFrom(r[0]);
        vo.setRangeTo(r[1]);
        return vo;
    }

    public List<PromoDailyVo> trend(String from, String to, String planType) {
        String[] r = normalizeRange(from, to, LocalDate.now());
        return promoReportMapper.selectTrend(r[0], r[1], normalizeChoice(planType, PLAN_TYPES, "all"));
    }

    public List<PromoPlanVo> plans(String from, String to, String planType) {
        String[] r = normalizeRange(from, to, LocalDate.now());
        return promoReportMapper.selectPlans(r[0], r[1], normalizeChoice(planType, PLAN_TYPES, "all"));
    }

    public IPage<PromoItemVo> items(long pageNum, long pageSize, String from, String to, String planType,
                                    String campaignId, String keyword, String facet, String sort) {
        String[] r = normalizeRange(from, to, LocalDate.now());
        Page<PromoItemVo> page = PageQueryUtil.of(pageNum, pageSize);
        // 关 count 优化：宝贝维度是「先聚合再筛」的派生表，优化器剥掉 group by 后
        // 外层 WHERE 会引用到不存在的别名（商品运营台踩过同样的坑）
        page.setOptimizeCountSql(false);
        return promoReportMapper.selectItems(page, r[0], r[1],
                normalizeChoice(planType, PLAN_TYPES, "all"),
                campaignId == null || campaignId.isBlank() ? null : campaignId.trim(),
                keyword == null || keyword.isBlank() ? null : keyword.trim(),
                normalizeChoice(facet, FACETS, "all"),
                normalizeChoice(sort, SORTS, "charge"));
    }

    /** 宝贝维度各筛选项的条数：一次查完，口径与 items 一致 */
    public java.util.Map<String, Object> itemFacetCounts(String from, String to, String planType,
                                                         String campaignId, String keyword) {
        String[] r = normalizeRange(from, to, LocalDate.now());
        String pt = normalizeChoice(planType, PLAN_TYPES, "all");
        String cid = campaignId == null || campaignId.isBlank() ? null : campaignId.trim();
        String kw = keyword == null || keyword.isBlank() ? null : keyword.trim();
        java.util.Map<String, Object> out = new java.util.LinkedHashMap<>();
        out.put("all", countItems(r, pt, cid, kw, "all"));
        out.put("noDeal", countItems(r, pt, cid, kw, "noDeal"));
        out.put("orphan", countItems(r, pt, cid, kw, "orphan"));
        out.put("unpriced", countItems(r, pt, cid, kw, "unpriced"));
        return out;
    }

    private long countItems(String[] r, String planType, String campaignId, String keyword, String facet) {
        Page<PromoItemVo> page = new Page<>(1, 1);
        page.setOptimizeCountSql(false);
        page.setSearchCount(true);
        IPage<PromoItemVo> res = promoReportMapper.selectItems(page, r[0], r[1], planType,
                campaignId, keyword, facet, "charge");
        return res.getTotal();
    }
}
