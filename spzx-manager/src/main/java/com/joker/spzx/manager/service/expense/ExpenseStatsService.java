package com.joker.spzx.manager.service.expense;

import com.joker.spzx.manager.mapper.ExpenseOrderMapper;
import com.joker.spzx.model.vo.expense.DailyAmountVo;
import com.joker.spzx.model.vo.expense.SummaryVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.temporal.TemporalAdjusters;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class ExpenseStatsService {

    @Autowired
    private ExpenseOrderMapper expenseOrderMapper;

    public SummaryVo summary(int days) {
        LocalDate today = LocalDate.now();
        SummaryVo vo = new SummaryVo();

        vo.setToday(expenseOrderMapper.sumBetween(today, today));
        vo.setLast7(expenseOrderMapper.sumBetween(today.minusDays(6), today));
        vo.setLast30(expenseOrderMapper.sumBetween(today.minusDays(29), today));
        vo.setMonthTotal(expenseOrderMapper.sumBetween(today.withDayOfMonth(1), today));
        vo.setCount30(expenseOrderMapper.countBetween(today.minusDays(29), today));

        BigDecimal last30 = vo.getLast30() == null ? BigDecimal.ZERO : vo.getLast30();
        vo.setDailyAvg30(last30.divide(BigDecimal.valueOf(30), 2, RoundingMode.HALF_UP));

        // 单日最高（近 days 天）
        DailyAmountVo maxDay = expenseOrderMapper.maxDaySince(today.minusDays(days - 1L));
        if (maxDay != null && maxDay.getAmount() != null
                && maxDay.getAmount().signum() > 0) {
            SummaryVo.MaxDay md = new SummaryVo.MaxDay();
            md.setDate(maxDay.getDate());
            md.setAmount(maxDay.getAmount());
            Map<String, Object> top = expenseOrderMapper.topOrderOfDay(maxDay.getDate());
            if (top != null) {
                Object title = top.get("title");
                Object cp = top.get("counterparty");
                md.setTopTitle(title == null ? null : title.toString());
                Object oid = top.get("id");
                String tag = oid == null ? null : expenseOrderMapper.firstTagNameOfOrder(Long.valueOf(oid.toString()));
                md.setTopTag(tag != null ? tag : (cp == null ? null : cp.toString()));
            }
            vo.setMaxDay(md);
        }

        // 月环比：本月1日至今 vs 上月1日至同日号
        LocalDate monthStart = today.withDayOfMonth(1);
        LocalDate prevMonthSameDay = today.minusMonths(1);
        LocalDate prevMonthStart = prevMonthSameDay.with(TemporalAdjusters.firstDayOfMonth());
        vo.setMonthMoM(compare(
                expenseOrderMapper.sumBetween(monthStart, today),
                expenseOrderMapper.sumBetween(prevMonthStart, prevMonthSameDay)));

        // 周环比：本周一至今 vs 上周同一星期几
        LocalDate monday = today.with(TemporalAdjusters.previousOrSame(java.time.DayOfWeek.MONDAY));
        LocalDate lastWeekSameDay = today.minusWeeks(1);
        LocalDate lastWeekMonday = lastWeekSameDay.with(TemporalAdjusters.previousOrSame(java.time.DayOfWeek.MONDAY));
        vo.setWeekWoW(compare(
                expenseOrderMapper.sumBetween(monday, today),
                expenseOrderMapper.sumBetween(lastWeekMonday, lastWeekSameDay)));

        vo.setLastImportDate(expenseOrderMapper.lastImportDate());
        return vo;
    }

    public List<DailyAmountVo> daily(int days) {
        LocalDate today = LocalDate.now();
        return expenseOrderMapper.sumDailySince(today.minusDays(days - 1L));
    }

    public List<Map<String, Object>> byTag(int days) {
        LocalDate begin = LocalDate.now().minusDays(days - 1L);
        List<Map<String, Object>> list = expenseOrderMapper.sumByTagSince(begin);
        return list == null ? List.of() : list;
    }

    public List<Map<String, Object>> byChannel(int days) {
        LocalDate begin = LocalDate.now().minusDays(days - 1L);
        List<Map<String, Object>> list = expenseOrderMapper.sumByChannelSince(begin);
        return list == null ? List.of() : list;
    }

    public List<Map<String, Object>> monthly(Integer year) {
        int y = year == null || year < 1970 || year > 2100 ? LocalDate.now().getYear() : year;
        List<Map<String, Object>> list = expenseOrderMapper.sumMonthly(
                LocalDate.of(y, 1, 1), LocalDate.of(y + 1, 1, 1));
        return list == null ? List.of() : list;
    }

    private SummaryVo.PeriodCompare compare(BigDecimal current, BigDecimal prev) {
        SummaryVo.PeriodCompare c = new SummaryVo.PeriodCompare();
        c.setCurrent(current == null ? BigDecimal.ZERO : current);
        c.setPrev(prev == null ? BigDecimal.ZERO : prev);
        if (c.getPrev().signum() > 0) {
            c.setPct(c.getCurrent().subtract(c.getPrev())
                    .multiply(BigDecimal.valueOf(100))
                    .divide(c.getPrev(), 1, RoundingMode.HALF_UP));
        }
        return c;
    }
}
