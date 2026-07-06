package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ProductSpecMapper;
import com.joker.spzx.manager.service.ProductSpecService;
import com.joker.spzx.model.entity.product.ProductSpec;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 商品规格 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class ProductSpecServiceImpl extends ServiceImpl<ProductSpecMapper, ProductSpec> implements ProductSpecService {

    @Override
    public IPage<ProductSpec> findByPage(Integer pageNum, Integer limit, Integer platformType) {
        LambdaQueryWrapper<ProductSpec> queryWrapper = new LambdaQueryWrapper<ProductSpec>()
                .eq(ProductSpec::getPlatformType, platformType)
                .eq(ProductSpec::getIsDeleted, 0)
                .orderByDesc(ProductSpec::getCreateTime);
        IPage<ProductSpec> page = new Page<>(pageNum, limit);
        list(page, queryWrapper);
        return page;
    }

    @Override
    @CacheEvict(cacheNames = "productSpec:all", allEntries = true)
    public void saveData(ProductSpec productSpec) {
        productSpec.setIsDeleted(0);
        productSpec.setCreateTime(LocalDateTime.now());
        productSpec.insert();
    }

    @Override
    @CacheEvict(cacheNames = "productSpec:all", allEntries = true)
    public void deleteById(Long id) {
        ProductSpec productSpec = new ProductSpec();
        productSpec.setId(id);
        productSpec.setIsDeleted(1);
        productSpec.updateById();
    }

    @Override
    @CacheEvict(cacheNames = "productSpec:all", allEntries = true)
    public void updateData(ProductSpec productSpec) {
        productSpec.setUpdateTime(LocalDateTime.now());
        productSpec.updateById();
    }

    @Override
    @Cacheable(cacheNames = "productSpec:all", key = "#platformType", unless = "#result == null || #result.isEmpty()")
    public List<ProductSpec> findAll(Integer platformType) {
        LambdaQueryWrapper<ProductSpec> wrapper = new LambdaQueryWrapper<ProductSpec>()
                .eq(ProductSpec::getPlatformType, platformType)
                .eq(ProductSpec::getIsDeleted, 0);
        return list(wrapper);
    }
}
