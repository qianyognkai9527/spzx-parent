package com.joker.spzx.manager.service.expense;

import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

class AlipayBillCsvParserTest {

    private static final Path SAMPLE =
            Path.of("/Users/qyk9527/我的/支付宝交易明细(20260122-20260920).csv");

    @Test
    void realSample() throws Exception {
        assumeTrue(Files.exists(SAMPLE), "样例文件不存在，跳过");
        byte[] bytes = Files.readAllBytes(SAMPLE);
        AlipayBillCsvParser p = new AlipayBillCsvParser();
        AlipayBillCsvParser.ParseResult r = p.parse(bytes);

        // 与账单头部汇总对账：共2805笔 = 收入421 + 支出1932 + 不计收支452
        assertEquals(2805, r.total, "数据行总数");
        assertEquals(873, r.skippedNonExpense, "收入+不计收支跳过数");
        assertEquals(13, r.skippedClosed, "交易关闭跳过数");
        assertEquals(11, r.skippedZero, "0元支出行跳过数");
        assertEquals(0, r.errors.size(), "解析错误应为0: " + r.errors);
        assertEquals(1908, r.rows.size(), "入库行数 = 1932支出 - 13关闭 - 11零元");

        // 交易订单号唯一
        Set<String> nos = new HashSet<>();
        r.rows.forEach(row -> nos.add(row.tradeNo));
        assertEquals(r.rows.size(), nos.size(), "交易订单号应唯一");

        // 金额全为正
        r.rows.forEach(row -> assertTrue(row.amount.signum() > 0));
    }

    @Test
    void syntheticCsvWithQuotesAndTabs() {
        String csv = String.join("\r\n",
                "----",
                "导出信息：",
                "共2笔记录",
                "",
                "特别提示：",
                "",
                "交易时间,交易分类,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注,",
                "2026-09-01 12:00:00,餐饮美食,x,\"含,逗号，含\"\"引号\"\"\",支出,12.50,余额宝\t,交易成功,\t20260901\t,,",
                "2026-09-01 13:00:00,转账红包,y,退款给某人,收入,3.00,余额\t,退款成功,\t20260902\t,,",
                "2026-09-01 14:00:00,其他,z,未完成订单,支出,99.00,余额\t,交易关闭,\t20260903\t,,",
                "");
        AlipayBillCsvParser p = new AlipayBillCsvParser();
        AlipayBillCsvParser.ParseResult r = p.parseRecords(p.splitRecords(csv));

        assertEquals(3, r.total, "3条数据行");
        assertEquals(1, r.skippedNonExpense, "收入行跳过");
        assertEquals(1, r.skippedClosed, "交易关闭跳过");
        assertEquals(1, r.rows.size(), "入库1条");
        AlipayBillCsvParser.ParsedRow row = r.rows.get(0);
        assertEquals("2026-09-01", row.expenseDate.toString());
        assertEquals("12.50", row.amount.toPlainString());
        // 引号内逗号/转义引号 + 尾部 \t 均正确处理
        assertEquals("含,逗号，含\"引号\"", row.title);
        assertEquals("20260901", row.tradeNo);
    }

    @Test
    void missingHeaderFails() {
        List<List<String>> bad = List.of(List.of("随便", "什么"), List.of("没有", "表头"));
        AlipayBillCsvParser p = new AlipayBillCsvParser();
        try {
            p.parseRecords(bad);
            throw new AssertionError("应当抛出 IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("交易时间"));
        }
    }
}
