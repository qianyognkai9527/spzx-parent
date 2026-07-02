package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.product.ProductFactoryPageParam;
import com.joker.spzx.model.entity.oper.MallProductFactory;

import java.util.List;

/**
 * <p>
 * 工厂基本信息表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
public interface MallProductFactoryService extends IService<MallProductFactory> {

    IPage<MallProductFactory> pageList(ProductFactoryPageParam pageParam);

    void saveData(MallProductFactory mallProductFactory);

    void updateData(MallProductFactory mallProductFactory);

    List<MallProductFactory> getAllProductFactory(Integer platformType);


}
