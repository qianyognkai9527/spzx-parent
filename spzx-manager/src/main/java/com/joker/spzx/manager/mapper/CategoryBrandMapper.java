package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.dto.product.CategoryBrandDto;
import com.joker.spzx.model.entity.product.Brand;
import com.joker.spzx.model.entity.product.CategoryBrand;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * <p>
 * 分类品牌 Mapper 接口
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Mapper
public interface CategoryBrandMapper extends BaseMapper<CategoryBrand> {

    IPage<CategoryBrand> findByPage(@Param("page") IPage<CategoryBrand> page, @Param("categoryBrandDto") CategoryBrandDto categoryBrandDto);

    List<Brand> findBrandByCategoryId(@Param("categoryId") Long categoryId, @Param("platformType") Integer platformType);

}
