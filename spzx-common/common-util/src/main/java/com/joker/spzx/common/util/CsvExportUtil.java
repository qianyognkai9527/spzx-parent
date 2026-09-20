package com.joker.spzx.common.util;

import jakarta.servlet.http.HttpServletResponse;

import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

/**
 * CSV 导出工具
 */
public final class CsvExportUtil {

    private CsvExportUtil() {
    }

    /**
     * 设置 CSV 下载响应头并返回 UTF-8 PrintWriter
     */
    public static PrintWriter writeCsvHeaders(HttpServletResponse response, String fileName) throws java.io.IOException {
        String encoded = URLEncoder.encode(fileName, StandardCharsets.UTF_8).replaceAll("\\+", "%20");
        response.setContentType("text/csv;charset=utf-8");
        response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + encoded + ".csv");
        return new PrintWriter(new OutputStreamWriter(response.getOutputStream(), StandardCharsets.UTF_8));
    }

    /**
     * CSV 字段转义：引号翻倍，含逗号/引号/换行时用引号包裹，null 返回空串
     */
    public static String escapeCsv(String v) {
        if (v == null) {
            return "";
        }
        String s = v.replace("\"", "\"\"");
        if (s.contains(",") || s.contains("\"") || s.contains("\n")) {
            return "\"" + s + "\"";
        }
        return s;
    }
}
