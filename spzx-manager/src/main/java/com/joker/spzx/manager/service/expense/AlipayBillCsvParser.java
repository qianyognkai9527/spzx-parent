package com.joker.spzx.manager.service.expense;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 支付宝账单 CSV 解析器（纯 Java，无 Spring 依赖，便于单测）。
 * <p>
 * 实测格式（样例：支付宝交易明细(20260122-20260920).csv）：
 * - 编码 gb18030（gbk 兼容），无 BOM，混合 CRLF/LF
 * - 文件头为导出信息块 + 特别提示块，表头行以「交易时间」开头（样例在第 24 行）
 * - 表头列：交易时间,交易分类,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注,
 * - 数据行字段尾部常带 \t；文件尾无汇总行
 * <p>
 * 口径：只收「收/支=支出」；「交易关闭」的支出行跳过；收入/不计收支跳过。
 */
public class AlipayBillCsvParser {

    private static final DateTimeFormatter TXN_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 与 expense_order.amount DECIMAL(12,2) 对齐，超限行报错跳过而非回滚整个导入 */
    private static final BigDecimal AMOUNT_MAX = new BigDecimal("9999999999.99");

    /** 必需列名 → 缺失即报错 */
    private static final String[] REQUIRED_COLUMNS = {
            "交易时间", "收/支", "金额", "交易状态", "交易订单号"
    };

    public static class ParsedRow {
        public LocalDate expenseDate;
        public LocalDateTime txnTime;
        public BigDecimal amount;
        public String title;
        public String counterparty;
        public String tradeNo;
    }

    public static class ParseResult {
        public int total;                 // 表头之后的数据行数（含被口径过滤的）
        public int skippedNonExpense;     // 收入/不计收支
        public int skippedClosed;         // 交易关闭
        public int skippedZero;           // 金额为 0 的支出行
        public int skippedBlank;          // 空行
        public final List<String> errors = new ArrayList<>();
        public final List<ParsedRow> rows = new ArrayList<>();
    }

    /** 解析入口。编码与记录切分复用 CsvText（推广报表导出是同一类脏活） */
    public ParseResult parse(byte[] bytes) {
        String text = com.joker.spzx.manager.util.CsvText.decode(bytes);
        List<List<String>> records = com.joker.spzx.manager.util.CsvText.splitRecords(text);
        return parseRecords(records);
    }

    static String decode(byte[] bytes) {
        return com.joker.spzx.manager.util.CsvText.decode(bytes);
    }

    public ParseResult parseRecords(List<List<String>> records) {
        ParseResult result = new ParseResult();

        int headerIdx = -1;
        for (int i = 0; i < records.size(); i++) {
            List<String> rec = records.get(i);
            if (!rec.isEmpty() && "交易时间".equals(cell(rec, 0))) {
                headerIdx = i;
                break;
            }
        }
        if (headerIdx < 0) {
            throw new IllegalArgumentException("未找到表头行（应包含「交易时间」列），请确认导出的是支付宝账单明细 CSV");
        }

        Map<String, Integer> col = new HashMap<>();
        List<String> header = records.get(headerIdx);
        for (int i = 0; i < header.size(); i++) {
            col.putIfAbsent(cell(header, i), i);
        }
        for (String name : REQUIRED_COLUMNS) {
            if (!col.containsKey(name)) {
                throw new IllegalArgumentException("表头缺少必需列：「" + name + "」，实际列=" + header);
            }
        }

        for (int i = headerIdx + 1; i < records.size(); i++) {
            List<String> rec = records.get(i);
            if (isBlankRow(rec)) {
                result.skippedBlank++;
                continue;
            }
            result.total++;

            String inOut = cell(rec, col.get("收/支"));
            if (!"支出".equals(inOut)) {
                result.skippedNonExpense++;
                continue;
            }
            String tradeStatus = cell(rec, col.get("交易状态"));
            if ("交易关闭".equals(tradeStatus)) {
                result.skippedClosed++;
                continue;
            }

            ParsedRow row = new ParsedRow();
            String amtStr = cell(rec, col.get("金额")).replace(",", "");
            try {
                row.amount = new BigDecimal(amtStr);
            } catch (NumberFormatException e) {
                result.errors.add("第" + (i + 1) + "行：金额非法 " + amtStr);
                continue;
            }
            if (row.amount.signum() <= 0) {
                result.skippedZero++;
                continue;
            }
            if (row.amount.compareTo(AMOUNT_MAX) > 0) {
                result.errors.add("第" + (i + 1) + "行：金额超出可导入上限 " + AMOUNT_MAX.toPlainString() + "：" + amtStr);
                continue;
            }

            String txnStr = cell(rec, col.get("交易时间"));
            try {
                row.txnTime = LocalDateTime.parse(txnStr, TXN_FORMAT);
            } catch (DateTimeParseException e) {
                result.errors.add("第" + (i + 1) + "行：交易时间非法 " + txnStr);
                continue;
            }
            row.expenseDate = row.txnTime.toLocalDate();

            row.tradeNo = cell(rec, col.get("交易订单号"));
            if (row.tradeNo.isEmpty()) {
                result.errors.add("第" + (i + 1) + "行：交易订单号为空");
                continue;
            }

            Integer titleIdx = col.get("商品说明");
            row.title = titleIdx == null ? null : nullToNull(cell(rec, titleIdx));
            Integer cpIdx = col.get("交易分类");
            row.counterparty = cpIdx == null ? null : nullToNull(cell(rec, cpIdx));

            result.rows.add(row);
        }
        return result;
    }

    static List<List<String>> splitRecords(String text) {
        return com.joker.spzx.manager.util.CsvText.splitRecords(text);
    }

    private static boolean isBlankRow(List<String> rec) {
        return com.joker.spzx.manager.util.CsvText.isBlankRow(rec);
    }

    /** 取单元格并 trim（支付宝导出常带尾部 \t 与空格） */
    private static String cell(List<String> rec, int idx) {
        return com.joker.spzx.manager.util.CsvText.cell(rec, idx);
    }

    private static String nullToNull(String s) {
        return s == null || s.isEmpty() ? null : s;
    }
}
