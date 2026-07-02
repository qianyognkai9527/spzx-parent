package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.CategoryBrandMapper;
import com.joker.spzx.manager.service.CategoryBrandService;
import com.joker.spzx.model.dto.product.CategoryBrandDto;
import com.joker.spzx.model.entity.product.Brand;
import com.joker.spzx.model.entity.product.CategoryBrand;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 分类品牌 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class CategoryBrandServiceImpl extends ServiceImpl<CategoryBrandMapper, CategoryBrand> implements CategoryBrandService {

    @Override
    public IPage<CategoryBrand> findByPage(Integer page, Integer limit, CategoryBrandDto categoryBrandDto) {
        IPage<CategoryBrand> pageInfo = new Page<>(page, limit);
        this.baseMapper.findByPage(pageInfo, categoryBrandDto);

        return pageInfo;
    }

    @Override
    public List<Brand> findBrandByCategoryId(Long categoryId, Integer platformType) {

        return this.baseMapper.findBrandByCategoryId(categoryId, platformType);
    }
}
