package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.product.ProductBindQueryDto;
import com.joker.spzx.model.dto.product.ProductBindRelationDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.entity.product.ProductBindRelation;

import java.util.List;

/**
 * <p>
 * 商品属性表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-08-22 15:59:22
 */
public interface ProductBindRelationService extends IService<ProductBindRelation> {

    List<Product> findUnBindSourceProduct(ProductBindQueryDto keyword);

    void bindRelation(ProductBindRelationDto productBindRelationDto);

    List<Product> findBoundSourceProduct(Long productId);
}
