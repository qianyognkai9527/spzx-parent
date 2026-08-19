package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.oper.FeeBenchmark;
import com.joker.spzx.model.entity.oper.ProfitAnalysisRecord;

import java.util.List;

public interface ProfitAnalysisRecordService extends IService<ProfitAnalysisRecord> {
    void saveRecord(ProfitAnalysisRecord record);
    Page<ProfitAnalysisRecord> pageByProduct(Long productId, Integer pageNum, Integer pageSize);
    List<ProfitAnalysisRecord> listByProduct(Long productId);
    void deleteRecord(Long id);
    void batchDelete(List<Long> ids);
    void clearByProduct(Long productId);
    FeeBenchmark getFeeBenchmark(Integer platformType, String category);
}
