package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.product.CategoryBrandDto;
import com.joker.spzx.model.entity.product.Brand;
import com.joker.spzx.model.entity.product.CategoryBrand;

import java.util.List;

/**
 * <p>
 * 分类品牌 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
public interface CategoryBrandService extends IService<CategoryBrand> {

    IPage<CategoryBrand> findByPage(Integer page, Integer limit, CategoryBrandDto categoryBrandDto);

    List<Brand> findBrandByCategoryId(Long categoryId, Integer platformType);
}
