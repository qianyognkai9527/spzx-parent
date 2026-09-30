package com.joker.spzx.manager.util;

import org.junit.jupiter.api.Test;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * CsvText 是从 AlipayBillCsvParser 里提出来的共享件，这里锁住它的三件事：
 * 编码探测、引号内换行、越界取值不抛异常。支付宝与推广报表导出都靠它。
 */
class CsvTextTest {

    @Test
    void utf8正常解码() {
        byte[] bytes = "日期,计划名称\n2026-09-29,关键词标准计划".getBytes(StandardCharsets.UTF_8);
        assertTrue(CsvText.decode(bytes).contains("关键词标准计划"));
    }

    @Test
    void 带BOM时剥掉BOM() {
        byte[] body = "日期,花费".getBytes(StandardCharsets.UTF_8);
        byte[] withBom = new byte[3 + body.length];
        withBom[0] = (byte) 0xEF;
        withBom[1] = (byte) 0xBB;
        withBom[2] = (byte) 0xBF;
        System.arraycopy(body, 0, withBom, 3, body.length);
        assertEquals("日期,花费", CsvText.decode(withBom));
    }

    @Test
    void 非法utf8字节回退gb18030() {
        // 中文后台导出常见 gb18030：这些字节按 utf-8 解是非法序列
        byte[] gbk = "日期,计划名称".getBytes(Charset.forName("gb18030"));
        String decoded = CsvText.decode(gbk);
        assertTrue(decoded.contains("计划名称"), () -> "回退失败，解出: " + decoded);
    }

    @Test
    void 引号内的逗号与换行不算分隔() {
        List<List<String>> recs = CsvText.splitRecords("标题,备注\n\"a,b\",\"行1\n行2\"");
        assertEquals(2, recs.size());
        assertEquals("a,b", recs.get(1).get(0));
        assertEquals("行1\n行2", recs.get(1).get(1));
    }

    @Test
    void 引号字段内的转义双引号还原() {
        // RFC4180：连续两个引号只在"被引号包住的字段"内部才是转义，裸字段开头的引号不在此列
        List<List<String>> recs = CsvText.splitRecords("\"他说\"\"清楚\"\"了\",1");
        assertEquals("他说\"清楚\"了", recs.get(0).get(0));
        assertEquals("1", recs.get(0).get(1));
    }

    @Test
    void 混合换行符与CRLF() {
        List<List<String>> recs = CsvText.splitRecords("a,b\r\nc,d\ne,f");
        assertEquals(3, recs.size());
        assertEquals("c", recs.get(1).get(0));
        assertEquals("e", recs.get(2).get(0));
    }

    @Test
    void 越界与null单元格返回空串而不是抛异常() {
        List<String> rec = List.of("a", "b");
        assertEquals("b", CsvText.cell(rec, 1));
        assertEquals("", CsvText.cell(rec, 9));
        assertEquals("", CsvText.cell(rec, -1));
    }

    @Test
    void 只有空白符的行算空行() {
        assertTrue(CsvText.isBlankRow(List.of("", "  ", "\t")));
        assertFalse(CsvText.isBlankRow(List.of("", "0")));
    }
}
