package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.oper.MallProductLink;

/**
 * <p>
 * 商品和货源关系表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
public interface MallProductLinkService extends IService<MallProductLink> {

    IPage<MallProductLink> pageList(Integer pageNum, Integer pageSize, Integer platformType);

    void saveData(MallProductLink mallProductLink);

    void updateData(MallProductLink mallProductLink);
}
