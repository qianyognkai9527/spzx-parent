package com.joker.spzx.manager.service.promo;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.joker.spzx.manager.mapper.PromoCostDailyMapper;
import com.joker.spzx.manager.mapper.PromoCostItemDailyMapper;
import com.joker.spzx.manager.mapper.PromoImportMapMapper;
import com.joker.spzx.model.entity.promo.PromoCostDaily;
import com.joker.spzx.model.entity.promo.PromoCostItemDaily;
import com.joker.spzx.model.entity.promo.PromoImportMap;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 推广日报导入。
 *
 * 流程固定是"先预览、再落库"：预览会把识别到的列、命中的映射、**没映射上的列**、日期范围、
 * 花费合计都返回来，第一次拿到真实导出文件时靠这个输出补映射，不用改代码。
 * 落库走自然键 upsert，所以同一份文件重导、或改了映射再导，都是覆盖而不是堆重复行。
 */
@Service
public class PromoCostService {

    private static final int CHUNK = 500;
    private static final int ERROR_CAP = 50;
    private static final DateTimeFormatter BATCH_TS = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    private static final ObjectMapper JSON = new ObjectMapper();

    @Autowired
    private PromoImportMapMapper importMapMapper;

    @Autowired
    private PromoCostDailyMapper dailyMapper;

    @Autowired
    private PromoCostItemDailyMapper itemMapper;

    private final PromoReportCsvParser parser = new PromoReportCsvParser();

    /** 导入结果（dryRun 与实跑共用同一结构） */
    public static class ImportResult {
        public boolean dryRun;
        public String reportLevel;
        public String planType;
        public String importBatch;
        public int headerLine;
        public List<String> headers = new ArrayList<>();
        public Map<String, String> matched = new LinkedHashMap<>();
        public List<String> unmapped = new ArrayList<>();
        public List<String> unknownTargets = new ArrayList<>();
        public List<String> missingRequired = new ArrayList<>();
        public int parsedRows;
        public int blankRows;
        public int inserted;
        public int overwritten;
        public LocalDate dateFrom;
        public LocalDate dateTo;
        public BigDecimal chargeSum = BigDecimal.ZERO;
        public List<String> errors = new ArrayList<>();
    }

    /** 某一层当前生效的列名映射：源列名 → 目标字段 */
    public Map<String, String> columnMap(String reportLevel) {
        List<PromoImportMap> maps = importMapMapper.selectList(Wrappers.<PromoImportMap>lambdaQuery()
                .eq(PromoImportMap::getReportLevel, reportLevel)
                .eq(PromoImportMap::getStatus, 1));
        Map<String, String> out = new LinkedHashMap<>();
        for (PromoImportMap m : maps) {
            out.put(m.getSourceColumn().trim(), m.getTargetColumn().trim());
        }
        return out;
    }

    public List<PromoImportMap> listMappings(String reportLevel) {
        return importMapMapper.selectList(Wrappers.<PromoImportMap>lambdaQuery()
                .eq(reportLevel != null && !reportLevel.isBlank(), PromoImportMap::getReportLevel, reportLevel)
                .orderByAsc(PromoImportMap::getReportLevel)
                .orderByAsc(PromoImportMap::getId));
    }

    public PromoImportMap getMapping(Long id) {
        return importMapMapper.selectById(id);
    }

    public String validateMapping(PromoImportMap map) {
        if (map == null) {
            return "参数为空";
        }
        if (!"campaign".equals(map.getReportLevel()) && !"item".equals(map.getReportLevel())) {
            return "报表层级只能是 campaign 或 item";
        }
        if (map.getSourceColumn() == null || map.getSourceColumn().isBlank()) {
            return "原始列名不能为空";
        }
        String target = map.getTargetColumn() == null ? "" : map.getTargetColumn().trim();
        Set<String> allowed = PromoReportCsvParser.targetsOf(map.getReportLevel());
        if (!allowed.contains(target)) {
            return "目标字段「" + target + "」不在 " + map.getReportLevel() + " 层，可选："
                    + String.join(" / ", new java.util.TreeSet<>(allowed));
        }
        map.setSourceColumn(map.getSourceColumn().trim());
        map.setTargetColumn(target);
        return null;
    }

    /** 同一列名在同一层级只能指向一个字段，否则映射顺序会决定结果 */
    public String mappingConflict(PromoImportMap map) {
        Long hit = importMapMapper.selectCount(Wrappers.<PromoImportMap>lambdaQuery()
                .eq(PromoImportMap::getReportLevel, map.getReportLevel())
                .eq(PromoImportMap::getSourceColumn, map.getSourceColumn())
                .ne(map.getId() != null, PromoImportMap::getId, map.getId()));
        return hit != null && hit > 0 ? "「" + map.getSourceColumn() + "」在这个层级已经有映射了，请直接改那条" : null;
    }

    @Transactional(rollbackFor = Exception.class)
    public void saveMapping(PromoImportMap map) {
        map.setId(null);
        if (map.getVerified() == null) {
            map.setVerified(0);
        }
        if (map.getStatus() == null) {
            map.setStatus(1);
        }
        importMapMapper.insert(map);
    }

    @Transactional(rollbackFor = Exception.class)
    public void updateMapping(PromoImportMap map) {
        importMapMapper.updateById(map);
    }

    public void deleteMapping(Long id) {
        importMapMapper.deleteById(id);
    }

    /**
     * 导入一份报表。
     *
     * @param dryRun true 只做解析与映射体检，不写库
     */
    public ImportResult importCsv(byte[] bytes, String reportLevel, String planType, Long shopId,
                                  String reportSource, boolean dryRun) {
        String level = "item".equals(reportLevel) ? "item" : "campaign";
        ImportResult result = new ImportResult();
        result.dryRun = dryRun;
        result.reportLevel = level;
        result.planType = normalizePlanType(planType);
        result.importBatch = "promo-" + level + "-" + LocalDateTime.now().format(BATCH_TS);

        List<List<String>> records = com.joker.spzx.manager.util.CsvText.splitRecords(
                com.joker.spzx.manager.util.CsvText.decode(bytes));
        PromoReportCsvParser.Result parsed = parser.parseRecords(records, columnMap(level), level);
        result.headerLine = parsed.headerLine;
        result.headers = parsed.headers;
        result.matched = parsed.matched;
        result.unmapped = parsed.unmapped;
        result.unknownTargets = parsed.unknownTargets;
        result.missingRequired = parsed.missingRequired;
        result.blankRows = parsed.blankRows;
        result.errors.addAll(parsed.errors);
        if (!parsed.missingRequired.isEmpty()) {
            result.errors.add("缺少必需列映射：" + String.join("、", parsed.missingRequired)
                    + "。已识别到的列=" + parsed.headers);
            return result;
        }
        if (parsed.rows.isEmpty()) {
            result.errors.add("表头认出来了，但下面没有可解析的数据行");
            return result;
        }

        List<PromoCostDaily> campaignRows = new ArrayList<>();
        List<PromoCostItemDaily> itemRows = new ArrayList<>();
        for (PromoReportCsvParser.Row row : parsed.rows) {
            String rawJson = toJson(row.raw);
            if ("item".equals(level)) {
                PromoRowConverter.Converted<PromoCostItemDaily> c = PromoRowConverter.toItem(
                        row.values, row.lineNo, shopId, 1, result.planType, reportSource, result.importBatch, rawJson);
                collect(result, c.errors);
                if (c.entity != null) {
                    itemRows.add(c.entity);
                }
            } else {
                PromoRowConverter.Converted<PromoCostDaily> c = PromoRowConverter.toCampaign(
                        row.values, row.lineNo, shopId, 1, result.planType, reportSource, result.importBatch, rawJson);
                collect(result, c.errors);
                if (c.entity != null) {
                    campaignRows.add(c.entity);
                }
            }
        }
        result.parsedRows = "item".equals(level) ? itemRows.size() : campaignRows.size();
        for (PromoCostDaily r : campaignRows) {
            accumulate(result, r.getStatDate(), r.getCharge());
        }
        for (PromoCostItemDaily r : itemRows) {
            accumulate(result, r.getStatDate(), r.getCharge());
        }

        if (dryRun || itemRows.isEmpty() && campaignRows.isEmpty()) {
            return result;
        }
        long before = count(level, shopId, result.planType);
        int affected = "item".equals(level) ? writeItems(itemRows) : writeCampaigns(campaignRows);
        long after = count(level, shopId, result.planType);
        // 用行数差算新增，剩下的就是覆盖：ON DUPLICATE KEY UPDATE 的 affected 每行 insert 记 1、update 记 2，
        // 单看 affected 分不出两者
        result.inserted = (int) Math.max(0, after - before);
        result.overwritten = Math.max(0, result.parsedRows - result.inserted);
        if (affected == 0) {
            result.errors.add("语句执行了但影响行数为 0，请检查表是否存在触发器或权限问题");
        }
        return result;
    }

    /** 整批回滚：一次导错的文件按批次号删掉，比逐行修快 */
    @Transactional(rollbackFor = Exception.class)
    public int deleteBatch(String importBatch) {
        if (importBatch == null || importBatch.isBlank()) {
            return 0;
        }
        int n = dailyMapper.delete(new LambdaQueryWrapper<PromoCostDaily>()
                .eq(PromoCostDaily::getImportBatch, importBatch.trim()));
        n += itemMapper.delete(new LambdaQueryWrapper<PromoCostItemDaily>()
                .eq(PromoCostItemDaily::getImportBatch, importBatch.trim()));
        return n;
    }

    private int writeCampaigns(List<PromoCostDaily> rows) {
        int affected = 0;
        for (int from = 0; from < rows.size(); from += CHUNK) {
            affected += dailyMapper.upsertBatch(new ArrayList<>(rows.subList(from, Math.min(rows.size(), from + CHUNK))));
        }
        return affected;
    }

    private int writeItems(List<PromoCostItemDaily> rows) {
        int affected = 0;
        for (int from = 0; from < rows.size(); from += CHUNK) {
            affected += itemMapper.upsertBatch(new ArrayList<>(rows.subList(from, Math.min(rows.size(), from + CHUNK))));
        }
        return affected;
    }

    private long count(String level, Long shopId, String planType) {
        long shop = shopId == null ? 0L : shopId;
        if ("item".equals(level)) {
            return itemMapper.selectCount(Wrappers.<PromoCostItemDaily>lambdaQuery()
                    .eq(PromoCostItemDaily::getShopId, shop)
                    .eq(PromoCostItemDaily::getPlanType, planType));
        }
        return dailyMapper.selectCount(Wrappers.<PromoCostDaily>lambdaQuery()
                .eq(PromoCostDaily::getShopId, shop)
                .eq(PromoCostDaily::getPlanType, planType));
    }

    private void collect(ImportResult result, List<String> errors) {
        for (String e : errors) {
            if (result.errors.size() < ERROR_CAP) {
                result.errors.add(e);
            }
        }
    }

    private void accumulate(ImportResult result, LocalDate date, BigDecimal charge) {
        if (date == null) {
            return;
        }
        if (result.dateFrom == null || date.isBefore(result.dateFrom)) {
            result.dateFrom = date;
        }
        if (result.dateTo == null || date.isAfter(result.dateTo)) {
            result.dateTo = date;
        }
        result.chargeSum = result.chargeSum.add(charge == null ? BigDecimal.ZERO : charge);
    }

    private static String normalizePlanType(String planType) {
        if (planType == null || planType.isBlank()) {
            return "other";
        }
        String v = planType.trim().toLowerCase();
        return Set.of("keyword", "crowd", "site", "other").contains(v) ? v : "other";
    }

    private static String toJson(Map<String, String> raw) {
        try {
            return JSON.writeValueAsString(raw);
        } catch (Exception e) {
            // 原始行留底失败不该阻断导入，事实数据本身已经拿到了
            return null;
        }
    }
}
