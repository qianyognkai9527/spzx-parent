package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.BrandMapper;
import com.joker.spzx.manager.service.BrandService;
import com.joker.spzx.model.entity.product.Brand;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 分类品牌 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:06:15
 */
@Service
public class BrandServiceImpl extends ServiceImpl<BrandMapper, Brand> implements BrandService {

    @Override
    public IPage<Brand> findByPage(Integer pageNum, Integer limit, Integer platformType) {
        IPage<Brand> page = new Page<>(pageNum, limit);
        LambdaQueryWrapper<Brand> wrapper = new LambdaQueryWrapper<Brand>()
                .eq(Brand::getPlatformType, platformType)
                .eq(Brand::getIsDeleted, 0)
                .orderByDesc(Brand::getCreateTime);
        page(page, wrapper);
        return page;
    }

    @Override
    public List<Brand> findAll(Integer platformType) {
        LambdaQueryWrapper<Brand> wrapper = new LambdaQueryWrapper<Brand>()
                .eq(Brand::getPlatformType, platformType)
                .eq(Brand::getIsDeleted, 0);
        return list(wrapper);
    }
}
