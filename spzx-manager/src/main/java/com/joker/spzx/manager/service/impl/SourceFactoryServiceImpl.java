package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SourceFactoryMapper;
import com.joker.spzx.manager.service.SourceFactoryService;
import com.joker.spzx.model.dto.product.SourceFactoryPageParam;
import com.joker.spzx.model.entity.product.SourceFactory;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 爬虫工厂排行榜 服务实现类
 * </p>
 *
 * @author joker
 */
@Service
public class SourceFactoryServiceImpl extends ServiceImpl<SourceFactoryMapper, SourceFactory> implements SourceFactoryService {

    @Override
    public IPage<SourceFactory> pageList(SourceFactoryPageParam pageParam) {
        IPage<SourceFactory> page = pageParam.getPage();
        LambdaQueryWrapper<SourceFactory> wrapper = lambdaQuery().getWrapper()
                .eq(pageParam.getPlatformType() != null, SourceFactory::getPlatformType, pageParam.getPlatformType())
                .like(StringUtils.isNotBlank(pageParam.getFactoryName()), SourceFactory::getFactoryName, pageParam.getFactoryName())
                .eq(StringUtils.isNotBlank(pageParam.getCategoryName()), SourceFactory::getCategoryName, pageParam.getCategoryName())
                .eq(StringUtils.isNotBlank(pageParam.getQualityGrade()), SourceFactory::getQualityGrade, pageParam.getQualityGrade())
                .eq(SourceFactory::getIsDeleted, 0);
        // 排序(默认按平均回头率降序)
        String sortField = pageParam.getSortField();
        String sortOrder = pageParam.getSortOrder();
        String secondary;
        if (sortField == null || "avgRepurchaseRate".equals(sortField)) {
            secondary = "avg_repurchase_rate";
        } else if ("trustYears".equals(sortField)) {
            secondary = "trust_years";
        } else if ("productCount".equals(sortField)) {
            secondary = "product_count";
        } else if ("totalSales".equals(sortField)) {
            secondary = "total_sales";
        } else {
            secondary = "avg_repurchase_rate";
        }
        String dir = "asc".equalsIgnoreCase(sortOrder) ? "ASC" : "DESC";
        // 优质等级优先(A>B>NULL), 再按指定字段
        wrapper.last("ORDER BY CASE WHEN quality_grade='A' THEN 1 WHEN quality_grade='B' THEN 2 ELSE 3 END ASC, "
                + secondary + " " + dir);
        page(page, wrapper);
        return page;
    }

    @Override
    public void saveData(SourceFactory sourceFactory) {
        if (sourceFactory.getIsDeleted() == null) {
            sourceFactory.setIsDeleted(0);
        }
        if (sourceFactory.getPlatformType() == null) {
            sourceFactory.setPlatformType(1);
        }
        sourceFactory.setCreateTime(LocalDateTime.now());
        save(sourceFactory);
    }

    @Override
    public void updateData(SourceFactory sourceFactory) {
        sourceFactory.setUpdateTime(LocalDateTime.now());
        updateById(sourceFactory);
    }

    @Override
    public List<SourceFactory> getAll(Integer platformType) {
        LambdaQueryWrapper<SourceFactory> wrapper = lambdaQuery().getWrapper()
                .eq(platformType != null, SourceFactory::getPlatformType, platformType)
                .eq(SourceFactory::getIsDeleted, 0)
                .orderByDesc(SourceFactory::getAvgRepurchaseRate);
        return list(wrapper);
    }

    @Override
    public void deleteById(Long id) {
        SourceFactory factory = getById(id);
        if (factory != null) {
            factory.setIsDeleted(1);
            factory.setUpdateTime(LocalDateTime.now());
            updateById(factory);
        }
    }
}
