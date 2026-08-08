package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.oper.MallProduct;

import java.util.List;

/**
 * <p>
 * 商品基本表 服务类
 * </p>
 *
 * @author joker
 * @since 2024-04-23 23:33:23
 */
public interface MallProductService extends IService<MallProduct> {

    IPage<MallProduct> pageList(Integer pageNum, Integer pageSize, Integer platformType, String keyword, String createTimeBegin, String createTimeEnd);

    List<MallProduct> listByPlatformType(Integer platformType);

    void saveData(MallProduct mallProduct);

    void updateData(MallProduct mallProduct);
}
