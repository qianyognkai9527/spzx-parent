package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductSkuMapper;
import com.joker.spzx.manager.service.MallProductSkuService;
import com.joker.spzx.model.entity.oper.MallProductSku;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 商品sku表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-05-08 14:13:08
 */
@Service
public class MallProductSkuServiceImpl extends ServiceImpl<MallProductSkuMapper, MallProductSku> implements MallProductSkuService {

    @Override
    public List<MallProductSku> getList(Long productId, Integer platformType) {
        LambdaQueryWrapper<MallProductSku> eq = lambdaQuery().getWrapper()
                .eq(MallProductSku::getPlatformType, platformType)
                .eq(MallProductSku::getProductId, productId)
                .eq(MallProductSku::getDelFlag, 0)
                .orderByDesc(MallProductSku::getUpdateTime);
        return list(eq);
    }

    @Override
    public void saveSku(MallProductSku sku) {
        sku.setCreateBy(AuthContextUtil.getUser().getId());
        sku.setUpdateTime(LocalDateTime.now());
        sku.setDelFlag(0);
        sku.insert();
    }
}
