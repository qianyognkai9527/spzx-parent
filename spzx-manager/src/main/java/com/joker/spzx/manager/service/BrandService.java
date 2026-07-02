package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.product.Brand;

import java.util.List;

/**
 * <p>
 * 分类品牌 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:06:15
 */
public interface BrandService extends IService<Brand> {

    IPage<Brand> findByPage(Integer page, Integer limit, Integer platformType);

    List<Brand> findAll(Integer platformType);
}
