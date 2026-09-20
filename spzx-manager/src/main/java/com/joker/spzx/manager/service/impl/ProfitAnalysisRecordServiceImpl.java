package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.FeeBenchmarkMapper;
import com.joker.spzx.common.util.SqlConstants;
import com.joker.spzx.manager.mapper.ProfitAnalysisRecordMapper;
import com.joker.spzx.manager.service.ProfitAnalysisRecordService;
import com.joker.spzx.model.entity.oper.FeeBenchmark;
import com.joker.spzx.model.entity.oper.ProfitAnalysisRecord;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class ProfitAnalysisRecordServiceImpl
        extends ServiceImpl<ProfitAnalysisRecordMapper, ProfitAnalysisRecord>
        implements ProfitAnalysisRecordService {

    @Autowired
    private FeeBenchmarkMapper feeBenchmarkMapper;

    @Override
    public void saveRecord(ProfitAnalysisRecord record) {
        save(record);
    }

    @Override
    public Page<ProfitAnalysisRecord> pageByProduct(Long productId, Integer pageNum, Integer pageSize) {
        LambdaQueryWrapper<ProfitAnalysisRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProfitAnalysisRecord::getProductId, productId)
                .eq(ProfitAnalysisRecord::getIsDeleted, 0)
                .orderByDesc(ProfitAnalysisRecord::getCreateTime);
        return page(new Page<>(pageNum, pageSize), wrapper);
    }

    @Override
    public List<ProfitAnalysisRecord> listByProduct(Long productId) {
        LambdaQueryWrapper<ProfitAnalysisRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProfitAnalysisRecord::getProductId, productId)
                .eq(ProfitAnalysisRecord::getIsDeleted, 0)
                .orderByDesc(ProfitAnalysisRecord::getCreateTime);
        return list(wrapper);
    }

    @Override
    public void deleteRecord(Long id) {
        removeById(id);
    }

    @Override
    public void batchDelete(List<Long> ids) {
        removeByIds(ids);
    }

    @Override
    public void clearByProduct(Long productId) {
        LambdaQueryWrapper<ProfitAnalysisRecord> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ProfitAnalysisRecord::getProductId, productId);
        remove(wrapper);
    }

    @Override
    public FeeBenchmark getFeeBenchmark(Integer platformType, String category) {
        LambdaQueryWrapper<FeeBenchmark> w = new LambdaQueryWrapper<>();
        w.eq(FeeBenchmark::getPlatformType, platformType)
                .eq(category != null && !category.isEmpty(), FeeBenchmark::getCategoryName, category)
                .eq(FeeBenchmark::getIsDeleted, 0)
                .last(SqlConstants.LIMIT_1);
        FeeBenchmark hit = feeBenchmarkMapper.selectOne(w);
        if (hit != null) return hit;
        // 兜底：同平台任意类目
        w = new LambdaQueryWrapper<>();
        w.eq(FeeBenchmark::getPlatformType, platformType)
                .eq(FeeBenchmark::getIsDeleted, 0)
                .last(SqlConstants.LIMIT_1);
        return feeBenchmarkMapper.selectOne(w);
    }
}
