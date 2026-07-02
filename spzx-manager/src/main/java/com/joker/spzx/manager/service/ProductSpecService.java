package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.product.ProductSpec;

import java.util.List;

/**
 * <p>
 * 商品规格 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
public interface ProductSpecService extends IService<ProductSpec> {

    IPage<ProductSpec> findByPage(Integer page, Integer limit, Integer platformType);

    void saveData(ProductSpec productSpec);

    void deleteById(Long id);

    void updateData(ProductSpec productSpec);

    List<ProductSpec> findAll(Integer platformType);

}
