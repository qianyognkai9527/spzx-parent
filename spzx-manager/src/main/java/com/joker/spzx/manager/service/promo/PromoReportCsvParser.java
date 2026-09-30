package com.joker.spzx.manager.service.promo;

import com.joker.spzx.manager.util.CsvText;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 推广报表 CSV 解析：列名映射由调用方传进来（promo_import_map 表），解析器本身不认识任何中文列名。
 *
 * 为什么这么设计：真实的万相台导出文件还没拿到手，列名、单位、是否有标题块都不知道。
 * 把"猜"集中在映射表这一份数据上，解析逻辑只处理确定性的事——编码、切分、数值归一化、
 * 以及**把没映射上的列原样报出来**，绝不静默丢字段。
 *
 * 纯 Java、无 Spring、无 DB，便于单测。
 */
public class PromoReportCsvParser {

    /** 计划级事实表允许被映射到的字段 */
    private static final Set<String> CAMPAIGN_TARGETS = Set.of(
            "stat_date", "campaign_id", "campaign_name",
            "charge", "ad_pv", "click", "ctr_percent", "cpc", "cpm",
            "gmv_total", "gmv_direct", "gmv_indirect", "order_total", "order_direct", "roi",
            "cart_count", "item_collect", "shop_collect", "chat_count",
            "unit_id", "unit_name");

    /** 明细级事实表允许的字段。entity_* 会顺带推出 dimension */
    private static final Set<String> ITEM_TARGETS = Set.of(
            "stat_date", "campaign_id", "campaign_name", "unit_id", "unit_name",
            "entity_id", "entity_name", "entity_keyword", "entity_crowd", "entity_item",
            "entity_creative", "entity_region", "item_id", "item_name",
            "charge", "ad_pv", "click", "ctr_percent", "cpc",
            "gmv_total", "gmv_direct", "gmv_indirect", "order_total", "roi",
            "cart_count", "item_collect", "chat_count");

    /** 明细行主标识的候选列，任一命中即可 */
    private static final List<String> ENTITY_TARGETS =
            List.of("entity_name", "entity_keyword", "entity_crowd", "entity_item",
                    "entity_creative", "entity_region", "entity_id");

    private static final Map<String, String> ENTITY_TARGET_DIMENSION = Map.of(
            "entity_keyword", "keyword",
            "entity_crowd", "crowd",
            "entity_item", "item",
            "entity_creative", "creative",
            "entity_region", "region");

    // M/d 而不是 MM/dd：导出里 2026-9-3 与 2026-09-03 都出现过，单位数写法会让严格格式解析失败
    private static final DateTimeFormatter[] DATE_FORMATS = {
            DateTimeFormatter.ofPattern("yyyy-M-d"),
            DateTimeFormatter.ofPattern("yyyy/M/d"),
            DateTimeFormatter.ofPattern("yyyy.M.d"),
            DateTimeFormatter.ofPattern("yyyyMMdd"),
    };

    /** 一行解析结果（已归一化成字符串，数值转换在 build 阶段做，便于逐字段报错） */
    public static class Row {
        public int lineNo;
        public final Map<String, String> values = new LinkedHashMap<>();
        public final Map<String, String> raw = new LinkedHashMap<>();
    }

    public static class Result {
        public List<String> headers = new ArrayList<>();
        public int headerLine;
        public Map<String, String> matched = new LinkedHashMap<>();
        public List<String> unmapped = new ArrayList<>();
        public List<String> unknownTargets = new ArrayList<>();
        public List<String> missingRequired = new ArrayList<>();
        public List<Row> rows = new ArrayList<>();
        public int totalRows;
        public int blankRows;
        public List<String> errors = new ArrayList<>();
    }

    /**
     * @param columnMap   源列名 → 目标字段（已按 report_level 过滤）
     * @param reportLevel campaign | item
     */
    public Result parse(byte[] bytes, Map<String, String> columnMap, String reportLevel) {
        return parseRecords(CsvText.splitRecords(CsvText.decode(bytes)), columnMap, reportLevel);
    }

    public Result parseRecords(List<List<String>> records, Map<String, String> columnMap, String reportLevel) {
        Set<String> allowed = "item".equals(reportLevel) ? ITEM_TARGETS : CAMPAIGN_TARGETS;
        Result result = new Result();

        int headerIdx = findHeaderRow(records, columnMap);
        if (headerIdx < 0) {
            result.errors.add("没找到表头行：文件里没有任何一列命中已配置的映射，请先在映射表里登记这份报表的列名");
            return result;
        }
        List<String> header = records.get(headerIdx);
        result.headerLine = headerIdx + 1;
        for (String name : header) {
            String key = name == null ? "" : name.trim();
            if (!key.isEmpty()) {
                result.headers.add(key);
            }
        }

        Map<Integer, String> colTarget = new LinkedHashMap<>();
        for (int i = 0; i < header.size(); i++) {
            String name = CsvText.cell(header, i);
            if (name.isEmpty()) {
                continue;
            }
            String target = columnMap.get(name);
            if (target == null) {
                result.unmapped.add(name);
            } else if (!allowed.contains(target)) {
                // 映射配了一个本层不认的字段：报出来，不要静默丢
                result.unknownTargets.add(name + " → " + target);
            } else {
                colTarget.put(i, target);
                result.matched.put(name, target);
            }
        }

        for (String required : requiredTargets(reportLevel)) {
            if (!result.matched.containsValue(required)) {
                result.missingRequired.add(required);
            }
        }
        if ("item".equals(reportLevel) && !anyMatched(result.matched, ENTITY_TARGETS)) {
            // 明细行的主标识可以来自六个列中的任意一个，缺整组才算不合格
            result.missingRequired.add("entity(关键词/人群/宝贝/创意/地域/主体ID 任一)");
        }

        for (int i = headerIdx + 1; i < records.size(); i++) {
            List<String> rec = records.get(i);
            if (CsvText.isBlankRow(rec)) {
                result.blankRows++;
                continue;
            }
            Row row = new Row();
            row.lineNo = i + 1;
            for (Map.Entry<Integer, String> e : colTarget.entrySet()) {
                row.values.put(e.getValue(), emptyToNull(CsvText.cell(rec, e.getKey())));
            }
            for (int c = 0; c < header.size() && c < rec.size(); c++) {
                row.raw.put(CsvText.cell(header, c), CsvText.cell(rec, c));
            }
            if (row.values.isEmpty() || row.values.values().stream().allMatch(v -> v == null)) {
                result.blankRows++;
                continue;
            }
            result.rows.add(row);
        }
        result.totalRows = result.rows.size();
        return result;
    }

    /** 表头 = 第一个命中已映射列名最多的那一行。不猜固定标记（"日期"之类），因为标题块长什么样还不知道 */
    private static int findHeaderRow(List<List<String>> records, Map<String, String> columnMap) {
        int best = -1;
        int bestHits = 0;
        for (int i = 0; i < Math.min(records.size(), 30); i++) {
            int hits = 0;
            for (String cell : records.get(i)) {
                if (cell != null && columnMap.containsKey(cell.trim())) {
                    hits++;
                }
            }
            if (hits > bestHits) {
                bestHits = hits;
                best = i;
            }
        }
        return bestHits >= 2 ? best : -1;
    }

    private static List<String> requiredTargets(String reportLevel) {
        return "item".equals(reportLevel)
                ? List.of("stat_date", "charge")
                : List.of("stat_date", "campaign_id", "charge");
    }

    private static boolean anyMatched(Map<String, String> matched, List<String> targets) {
        for (String v : matched.values()) {
            if (targets.contains(v)) {
                return true;
            }
        }
        return false;
    }

    // ==================== 值归一化（今晚拿到真实文件后最可能要调的就是这里） ====================

    /** 报表里的空值写法五花八门：-、--、/、暂无、null */
    public static String emptyToNull(String s) {
        if (s == null) {
            return null;
        }
        String v = s.trim();
        if (v.isEmpty() || v.equals("-") || v.equals("--") || v.equals("/") || v.equals("－")
                || v.equalsIgnoreCase("null") || v.equals("暂无") || v.equals("N/A") || v.equalsIgnoreCase("na")) {
            return null;
        }
        return v;
    }

    /**
     * 金额/比率：去掉货币符号与千分位；"1.2万"→12000、"3亿"→300000000；
     * 带百分号的按百分数原样返回（12.34% → 12.34），是否要再除以 100 由目标字段决定。
     */
    public static BigDecimal toDecimal(String raw) {
        String v = emptyToNull(raw);
        if (v == null) {
            return null;
        }
        v = v.replace("¥", "").replace("￥", "").replace(",", "").replace(" ", "").replace("元", "");
        BigDecimal multiplier = BigDecimal.ONE;
        if (v.endsWith("%")) {
            v = v.substring(0, v.length() - 1);
        } else if (v.endsWith("万")) {
            v = v.substring(0, v.length() - 1);
            multiplier = new BigDecimal("10000");
        } else if (v.endsWith("亿")) {
            v = v.substring(0, v.length() - 1);
            multiplier = new BigDecimal("100000000");
        }
        try {
            return new BigDecimal(v).multiply(multiplier);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** 计数类：四舍五入到整数；无法解析返回 null（区别于 0） */
    public static Long toLong(String raw) {
        BigDecimal d = toDecimal(raw);
        return d == null ? null : d.setScale(0, java.math.RoundingMode.HALF_UP).longValueExact();
    }

    /** 日期：支持 yyyy-MM-dd / yyyy/M/d / yyyyMMdd / yyyy.MM.dd，以及带时间的 "2026-09-30 00:00:00" */
    public static LocalDate toDate(String raw) {
        String v = emptyToNull(raw);
        if (v == null) {
            return null;
        }
        int space = v.indexOf(' ');
        if (space > 0) {
            v = v.substring(0, space);
        }
        v = v.replace('年', '-').replace('月', '-').replace('日', ' ').trim();
        for (DateTimeFormatter f : DATE_FORMATS) {
            try {
                return LocalDate.parse(v, f);
            } catch (java.time.format.DateTimeParseException ignored) {
                // 试下一种格式
            }
        }
        return null;
    }

    /** 明细行的 dimension：由映射到 entity_* 的列推出，都没命中则 other */
    public static String dimensionOf(Map<String, String> rowValues) {
        for (Map.Entry<String, String> e : ENTITY_TARGET_DIMENSION.entrySet()) {
            String v = rowValues.get(e.getKey());
            if (v != null && !v.isBlank()) {
                return e.getValue();
            }
        }
        return rowValues.getOrDefault("dimension", "other");
    }

    /** entity_key：有 id 用 id，否则用名称。关键词本身没有 id，所以必须留这条兜底 */
    public static String entityKeyOf(Map<String, String> rowValues) {
        String id = rowValues.get("entity_id");
        if (id != null && !id.isBlank()) {
            return id.trim();
        }
        for (String name : List.of("entity_name", "entity_keyword", "entity_crowd", "entity_item",
                "entity_creative", "entity_region")) {
            String v = rowValues.get(name);
            if (v != null && !v.isBlank()) {
                return v.trim();
            }
        }
        return null;
    }

    /** 明细行的 entity 名称：generic 列优先，其次各维度专用列 */
    public static String entityNameOf(Map<String, String> rowValues) {
        String name = rowValues.get("entity_name");
        if (name != null && !name.isBlank()) {
            return name.trim();
        }
        for (Map.Entry<String, String> e : ENTITY_TARGET_DIMENSION.entrySet()) {
            String v = rowValues.get(e.getKey());
            if (v != null && !v.isBlank()) {
                return v.trim();
            }
        }
        return null;
    }

    /** 供服务层复用的目标字段白名单视图 */
    public static Set<String> targetsOf(String reportLevel) {
        return "item".equals(reportLevel) ? new LinkedHashSet<>(ITEM_TARGETS) : new LinkedHashSet<>(CAMPAIGN_TARGETS);
    }
}
