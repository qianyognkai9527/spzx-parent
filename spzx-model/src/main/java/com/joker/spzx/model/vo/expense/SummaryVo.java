package com.joker.spzx.model.vo.expense;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
public class SummaryVo {

    private BigDecimal today;
    private BigDecimal last7;
    private BigDecimal last30;
    private BigDecimal monthTotal;

    /** 近30天笔数 */
    private Long count30;

    /** 近30天日均 = last30/30 */
    private BigDecimal dailyAvg30;

    private MaxDay maxDay;

    /** 月环比：本月1日至今 vs 上月1日至同日号 */
    private PeriodCompare monthMoM;

    /** 周环比：本周一至今 vs 上周同一星期几 */
    private PeriodCompare weekWoW;

    /** 已导入账单(source=1)的最新交易日期 */
    private LocalDate lastImportDate;

    @Data
    public static class MaxDay {
        private LocalDate date;
        private BigDecimal amount;
        /** 当天金额最大一笔的商品说明 */
        private String topTitle;
        /** 该笔的标签名（无标签取交易分类） */
        private String topTag;
    }

    @Data
    public static class PeriodCompare {
        private BigDecimal current;
        private BigDecimal prev;
        /** 涨跌百分比：(current-prev)/prev*100，prev=0 时为 null */
        private BigDecimal pct;
    }
}
