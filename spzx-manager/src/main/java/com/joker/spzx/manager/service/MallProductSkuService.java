package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.oper.MallProductSku;

import java.util.List;

/**
 * <p>
 * 商品sku表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-05-08 14:13:08
 */
public interface MallProductSkuService extends IService<MallProductSku> {

    List<MallProductSku> getList(Long productId, Integer platformType);

    void saveSku(MallProductSku sku);
}
