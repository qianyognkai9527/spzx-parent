package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ProductUnitMapper;
import com.joker.spzx.manager.service.ProductUnitService;
import com.joker.spzx.model.entity.system.ProductUnit;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 商品单位 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class ProductUnitServiceImpl extends ServiceImpl<ProductUnitMapper, ProductUnit> implements ProductUnitService {

    @Override
    @Cacheable(cacheNames = "productUnit:all", key = "'all'", unless = "#result == null || #result.isEmpty()")
    public List<ProductUnit> findAll() {
        LambdaQueryWrapper<ProductUnit> eq = lambdaQuery().getWrapper().eq(ProductUnit::getIsDeleted, 0);
        return this.baseMapper.selectList(eq);
    }
}
