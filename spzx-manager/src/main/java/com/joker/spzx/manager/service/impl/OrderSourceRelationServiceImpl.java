package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.util.PageQueryUtil;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.common.util.SqlConstants;
import com.joker.spzx.manager.mapper.OrderSourceRelationMapper;
import com.joker.spzx.manager.service.OrderSourceRelationService;
import com.joker.spzx.manager.service.ProductBindRelationService;
import com.joker.spzx.manager.service.ProductService;
import com.joker.spzx.model.entity.order.OrderSourceRelation;
import com.joker.spzx.model.entity.product.ProductBindRelation;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * <p>
 * 本地订单与货源订单关联 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-07-01 10:00:00
 */
@Service
public class OrderSourceRelationServiceImpl extends ServiceImpl<OrderSourceRelationMapper, OrderSourceRelation> implements OrderSourceRelationService {

    @Autowired
    private ProductBindRelationService productBindRelationService;

    @Autowired
    private ProductService productService;

    @Override
    public IPage<OrderSourceRelation> findByPage(Integer pageNum, Integer pageSize, OrderSourceRelation queryDto) {
        LambdaQueryWrapper<OrderSourceRelation> wrapper = new LambdaQueryWrapper<>();
        wrapper
                .eq(queryDto.getPlatformType() != null, OrderSourceRelation::getPlatformType, queryDto.getPlatformType())
                .eq(StringUtils.hasText(queryDto.getOrderNo()), OrderSourceRelation::getOrderNo, queryDto.getOrderNo())
                .eq(StringUtils.hasText(queryDto.getSourceOrderNo()), OrderSourceRelation::getSourceOrderNo, queryDto.getSourceOrderNo())
                .eq(queryDto.getPlatformProductId() != null, OrderSourceRelation::getPlatformProductId, queryDto.getPlatformProductId())
                .eq(queryDto.getSourceProductId() != null, OrderSourceRelation::getSourceProductId, queryDto.getSourceProductId())
                .eq(queryDto.getOrderStatus() != null, OrderSourceRelation::getOrderStatus, queryDto.getOrderStatus())
                .orderByDesc(OrderSourceRelation::getCreateTime);
        return PageQueryUtil.page(this, pageNum, pageSize, wrapper);
    }

    @Override
    public OrderSourceRelation getById(Long id) {
        LambdaQueryWrapper<OrderSourceRelation> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(OrderSourceRelation::getId, id);
        return getOne(wrapper);
    }

    @Override
    public void saveData(OrderSourceRelation orderSourceRelation) {
        // 校验唯一性：同一平台下，本地订单号+货源订单号不能重复
        checkDuplicate(orderSourceRelation, null);
        orderSourceRelation.setIsDeleted(0);
        save(orderSourceRelation);
    }

    @Override
    public void updateData(OrderSourceRelation orderSourceRelation) {
        // 校验唯一性：排除自身后，同一平台下同订单号不能重复
        checkDuplicate(orderSourceRelation, orderSourceRelation.getId());
        updateById(orderSourceRelation);
    }

    @Override
    public void deleteById(Long id) {
        this.removeById(id);
    }

    /**
     * 校验同一平台下，本地订单号 + 货源订单号是否已存在
     */
    private void checkDuplicate(OrderSourceRelation entity, Long excludeId) {
        LambdaQueryWrapper<OrderSourceRelation> wrapper = new LambdaQueryWrapper<>();
        wrapper
                .eq(OrderSourceRelation::getPlatformType, entity.getPlatformType())
                .eq(OrderSourceRelation::getOrderNo, entity.getOrderNo())
                .eq(OrderSourceRelation::getSourceOrderNo, entity.getSourceOrderNo())
                .ne(excludeId != null, OrderSourceRelation::getId, excludeId);
        long count = count(wrapper);
        if (count > 0) {
            throw new ServiceException(ResultCodeEnum.DATA_ERROR);
        }
    }

    /**
     * ②自动关联: 给定平台商品id, 查 ProductBindRelation -> source_product 自动回填货源侧(编码/标题/货源价/运费)
     */
    @Override
    public OrderSourceRelation autoFillByPlatformProduct(Long platformProductId) {
        OrderSourceRelation result = new OrderSourceRelation();
        result.setPlatformProductId(platformProductId);
        ProductBindRelation bind = productBindRelationService.getOne(
                new LambdaQueryWrapper<ProductBindRelation>()
                        .eq(ProductBindRelation::getProductId, platformProductId)
                        .eq(ProductBindRelation::getIsDeleted, 0)
                        .last(SqlConstants.LIMIT_1));
        if (bind == null) {
            return result;
        }
        Long sourceProductId = bind.getSourceProductid();
        Product source = productService.getById(sourceProductId);
        if (source == null) {
            return result;
        }
        result.setSourceProductId(sourceProductId);
        result.setSourceProductCode(source.getSourceProductCode());
        result.setSourceProductTitle(source.getSourceProductName());
        result.setSourceSellingPrice(source.getSourcePrice());
        result.setSourceFreight(source.getFreightCost());
        return result;
    }

}
