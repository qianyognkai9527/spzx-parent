package com.joker.spzx.manager.util;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * CSV 文本读取：编码探测 + RFC4180 记录切分。
 *
 * 从 AlipayBillCsvParser 里提出来，因为支付宝账单和推广报表导出是同一类脏活：
 * 中文导出常见 gb18030、字段里带逗号/换行/引号、行尾混 \r\n 与 \n、值里带制表符。
 */
public final class CsvText {

    private CsvText() {
    }

    /** BOM→utf-8；先严格试 utf-8，失败回退 gb18030（新 String(bytes,"gb18030") 对畸形字节只替换不抛异常，不能作为探测手段） */
    public static String decode(byte[] bytes) {
        if (bytes == null || bytes.length == 0) {
            return "";
        }
        if (bytes.length >= 3 && (bytes[0] & 0xFF) == 0xEF && (bytes[1] & 0xFF) == 0xBB && (bytes[2] & 0xFF) == 0xBF) {
            return new String(bytes, 3, bytes.length - 3, StandardCharsets.UTF_8);
        }
        try {
            return StandardCharsets.UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException e) {
            return new String(bytes, java.nio.charset.Charset.forName("gb18030"));
        }
    }

    /** 双引号包裹的字段内支持逗号/换行/转义双引号；兼容 \r\n 与 \n */
    public static List<List<String>> splitRecords(String text) {
        List<List<String>> records = new ArrayList<>();
        List<String> cur = new ArrayList<>();
        StringBuilder field = new StringBuilder();
        boolean inQuotes = false;
        boolean fieldStarted = false;

        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (inQuotes) {
                if (c == '"') {
                    if (i + 1 < text.length() && text.charAt(i + 1) == '"') {
                        field.append('"');
                        i++;
                    } else {
                        inQuotes = false;
                    }
                } else {
                    field.append(c);
                }
            } else {
                if (c == '"' && field.isEmpty()) {
                    inQuotes = true;
                    fieldStarted = true;
                } else if (c == ',') {
                    cur.add(field.toString());
                    field.setLength(0);
                    fieldStarted = false;
                } else if (c == '\r' || c == '\n') {
                    if (c == '\r' && i + 1 < text.length() && text.charAt(i + 1) == '\n') {
                        i++;
                    }
                    cur.add(field.toString());
                    field.setLength(0);
                    records.add(cur);
                    cur = new ArrayList<>();
                    fieldStarted = false;
                } else {
                    field.append(c);
                    fieldStarted = true;
                }
            }
        }
        if (field.length() > 0 || fieldStarted || !cur.isEmpty()) {
            cur.add(field.toString());
            records.add(cur);
        }
        return records;
    }

    /** 取单元格并 trim（中文后台导出常在值尾带 \t 与空格）；越界返回空串而不是抛异常 */
    public static String cell(List<String> rec, int idx) {
        if (idx < 0 || idx >= rec.size()) {
            return "";
        }
        String v = rec.get(idx);
        return v == null ? "" : v.trim();
    }

    public static boolean isBlankRow(List<String> rec) {
        for (String cell : rec) {
            if (!cell.trim().isEmpty()) {
                return false;
            }
        }
        return true;
    }
}
