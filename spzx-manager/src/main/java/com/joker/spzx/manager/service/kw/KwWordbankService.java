package com.joker.spzx.manager.service.kw;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.config.KwProperties;
import com.joker.spzx.manager.mapper.KwWordbankBatchMapper;
import com.joker.spzx.manager.mapper.KwWordbankItemMapper;
import com.joker.spzx.model.entity.kw.KwWordbankBatch;
import com.joker.spzx.model.entity.kw.KwWordbankItem;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
public class KwWordbankService {

    @Autowired
    private KwWordbankBatchMapper batchMapper;

    @Autowired
    private KwWordbankItemMapper itemMapper;

    @Autowired
    private KwProperties props;

    /**
     * 上传生意参谋导出 Excel（可多文件合并），解析→去重→过滤→打分→入库。
     * 列名宽松映射：表头含关键字即识别。
     */
    public Long upload(List<MultipartFile> files, String name, Integer platformType) {
        // keyword -> item（保持首次出现，人气取更大者）
        Map<String, KwWordbankItem> merged = new LinkedHashMap<>();
        List<String> fileNames = new ArrayList<>();
        try {
            for (MultipartFile f : files) {
                if (f == null || f.isEmpty()) {
                    continue;
                }
                fileNames.add(f.getOriginalFilename());
                parseFile(f, merged);
            }
        } catch (Exception e) {
            throw new RuntimeException("词表解析失败: " + e.getMessage(), e);
        }
        if (merged.isEmpty()) {
            throw new RuntimeException("未解析到任何词条，请检查文件格式（需含关键词/搜索人气列）");
        }

        // 硬过滤：搜索人气 < minPopularity 剔除
        List<KwWordbankItem> items = new ArrayList<>();
        for (KwWordbankItem it : merged.values()) {
            if (it.getSearchPopularity() != null
                    && it.getSearchPopularity() >= props.getMinPopularity()) {
                items.add(it);
            }
        }
        if (items.isEmpty()) {
            throw new RuntimeException("全部词条人气低于 " + props.getMinPopularity() + "，已全部过滤");
        }

        // 批内打分
        List<double[]> rows = new ArrayList<>();
        for (KwWordbankItem it : items) {
            rows.add(new double[]{
                    nz(it.getSearchPopularity()),
                    it.getClickRate() == null ? 0 : it.getClickRate().doubleValue(),
                    it.getConvRate() == null ? 0 : it.getConvRate().doubleValue(),
                    nz(it.getBuyerCount())
            });
        }
        double[] scores = KwScoreUtil.score(rows, props.getWeights());
        for (int i = 0; i < items.size(); i++) {
            items.get(i).setScore(BigDecimal.valueOf(scores[i]).setScale(4, RoundingMode.HALF_UP));
        }
        items.sort((a, b) -> b.getScore().compareTo(a.getScore()));

        // 入库
        KwWordbankBatch batch = new KwWordbankBatch();
        batch.setName(name);
        batch.setPlatformType(platformType == null ? 1 : platformType);
        batch.setFileNames(String.join(",", fileNames));
        batch.setWordCount(items.size());
        batchMapper.insert(batch);
        for (KwWordbankItem it : items) {
            it.setBatchId(batch.getId());
            itemMapper.insert(it);
        }
        log.info("词表批次入库: id={}, name={}, words={}", batch.getId(), name, items.size());
        return batch.getId();
    }

    /** EasyExcel 无模型读：所有行均进监听器（headRowNumber(0)），由监听器扫描表头行 */
    private void parseFile(MultipartFile f, Map<String, KwWordbankItem> merged) throws Exception {
        EasyExcel.read(f.getInputStream(), new AnalysisEventListenerAdapter(merged))
                .sheet().headRowNumber(0).doRead();
    }

    private double nz(Integer v) {
        return v == null ? 0 : v;
    }

    public List<KwWordbankBatch> batchList() {
        return batchMapper.selectList(
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<KwWordbankBatch>()
                        .orderByDesc(KwWordbankBatch::getId));
    }

    public IPage<KwWordbankItem> itemPage(Long batchId, long pageNum, long pageSize) {
        return itemMapper.selectPage(new Page<>(pageNum, pageSize),
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<KwWordbankItem>()
                        .eq(KwWordbankItem::getBatchId, batchId)
                        .orderByDesc(KwWordbankItem::getScore));
    }

    /** EasyExcel 监听器：首行表头做列名映射，数据行组装词条 */
    private static class AnalysisEventListenerAdapter
            implements com.alibaba.excel.read.listener.ReadListener<Map<Integer, String>> {

        private final Map<String, Integer> colIdx = new LinkedHashMap<>();
        private final Map<String, Integer> headerMap = new LinkedHashMap<>();
        private final Map<String, KwWordbankItem> merged;
        private int headerRow = -1;

        AnalysisEventListenerAdapter(Map<String, KwWordbankItem> merged) {
            this.merged = merged;
        }

        @Override
        public void invoke(Map<Integer, String> row, com.alibaba.excel.context.AnalysisContext ctx) {
            if (headerRow < 0) {
                // 还没锁定表头：找含"关键词/搜索词"的行
                boolean isHeader = row.values().stream()
                        .anyMatch(v -> v != null && (v.contains("关键词") || v.contains("搜索词")));
                if (!isHeader) {
                    return;
                }
                headerRow = ctx.readRowHolder().getRowIndex();
                row.forEach((k, v) -> {
                    if (v != null && !v.isBlank()) {
                        headerMap.put(v.trim(), k);
                    }
                });
                mapColumns();
                return;
            }
            String kw = str(row, colIdx.get("keyword"));
            if (kw == null || kw.isBlank()) {
                return;
            }
            KwWordbankItem it = new KwWordbankItem();
            it.setKeyword(kw);
            it.setSearchPopularity(intVal(str(row, colIdx.get("popularity"))));
            it.setClickRate(decVal(str(row, colIdx.get("clickRate"))));
            it.setConvRate(decVal(str(row, colIdx.get("convRate"))));
            it.setBuyerCount(intVal(str(row, colIdx.get("buyer"))));
            KwWordbankItem old = merged.get(kw);
            if (old == null || (it.getSearchPopularity() != null
                    && (old.getSearchPopularity() == null
                    || it.getSearchPopularity() > old.getSearchPopularity()))) {
                merged.put(kw, it);
            }
        }

        private void mapColumns() {
            for (Map.Entry<String, Integer> e : headerMap.entrySet()) {
                String h = e.getKey();
                Integer idx = e.getValue();
                if (h.contains("关键词") || h.contains("搜索词")) {
                    colIdx.put("keyword", idx);
                } else if (h.contains("搜索人气") || (h.contains("人气") && !colIdx.containsKey("popularity"))) {
                    colIdx.put("popularity", idx);
                } else if (h.contains("点击率") && !colIdx.containsKey("clickRate")) {
                    colIdx.put("clickRate", idx);
                } else if (h.contains("转化率") && !colIdx.containsKey("convRate")) {
                    colIdx.put("convRate", idx);
                } else if (h.contains("买家数") && !colIdx.containsKey("buyer")) {
                    colIdx.put("buyer", idx);
                }
            }
        }

        private String str(Map<Integer, String> row, Integer idx) {
            return idx == null ? null : row.get(idx);
        }

        private Integer intVal(String s) {
            if (s == null || s.isBlank()) {
                return null;
            }
            try {
                return (int) Double.parseDouble(s.replaceAll("[^0-9.\\-]", ""));
            } catch (Exception e) {
                return null;
            }
        }

        private BigDecimal decVal(String s) {
            if (s == null || s.isBlank()) {
                return null;
            }
            try {
                return new BigDecimal(s.replace("%", "").trim())
                        .divide(new BigDecimal(s.contains("%") ? "100" : "1"), 6, RoundingMode.HALF_UP);
            } catch (Exception e) {
                return null;
            }
        }

        @Override
        public void doAfterAllAnalysed(com.alibaba.excel.context.AnalysisContext ctx) {
        }
    }
}
