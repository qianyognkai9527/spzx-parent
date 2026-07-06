package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.ProductBindRelationMapper;
import com.joker.spzx.manager.mapper.ProductMapper;
import com.joker.spzx.manager.service.ProductBindRelationService;
import com.joker.spzx.model.dto.product.ProductBindQueryDto;
import com.joker.spzx.model.dto.product.ProductBindRelationDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.entity.product.ProductBindRelation;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * <p>
 * 商品属性表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-08-22 15:59:22
 */
@Service
public class ProductBindRelationServiceImpl extends ServiceImpl<ProductBindRelationMapper, ProductBindRelation> implements ProductBindRelationService {

    @Autowired
    private ProductMapper productMapper;

    @Override
    public List<Product> findUnBindSourceProduct(ProductBindQueryDto keyword) {
        LambdaQueryWrapper<Product> productQueryWrapper = new LambdaQueryWrapper<>();
        productQueryWrapper.eq(Product::getIsDeleted, 0)
                .like(StringUtils.isNotBlank(keyword.getSourceProductName()), Product::getSourceProductName, keyword);
        productQueryWrapper.orderByDesc(Product::getCreateTime);
        return productMapper.selectList(productQueryWrapper);
    }

    @Override
    public void bindRelation(ProductBindRelationDto productBindRelationDto) {
        ProductBindRelation relation = new ProductBindRelation();
        relation.setProductId(productBindRelationDto.getProductId());
        relation.setSourceProductid(productBindRelationDto.getSourceProductId());
        relation.setCreateTime(java.time.LocalDateTime.now());
        relation.setIsDeleted(0);
        relation.insert();
    }

    @Override
    public List<Product> findBoundSourceProduct(Long productId) {
        LambdaQueryWrapper<ProductBindRelation> relationWrapper = new LambdaQueryWrapper<>();
        relationWrapper.eq(ProductBindRelation::getProductId, productId)
                .eq(ProductBindRelation::getIsDeleted, 0);
        List<ProductBindRelation> relations = this.list(relationWrapper);
        if (relations.isEmpty()) {
            return java.util.Collections.emptyList();
        }
        List<Long> sourceProductIds = relations.stream()
                .map(ProductBindRelation::getSourceProductid)
                .collect(java.util.stream.Collectors.toList());
        LambdaQueryWrapper<Product> productWrapper = new LambdaQueryWrapper<>();
        productWrapper.in(Product::getId, sourceProductIds)
                .eq(Product::getIsDeleted, 0);
        return productMapper.selectList(productWrapper);
    }
}
