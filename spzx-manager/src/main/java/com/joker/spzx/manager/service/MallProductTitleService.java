package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.oper.MallProductTitle;

import java.util.List;

/**
 * <p>
 * 商品历史标题表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
public interface MallProductTitleService extends IService<MallProductTitle> {

    IPage<MallProductTitle> pageList(Integer pageNum, Integer pageSize);

    void saveData(MallProductTitle mallProductTitle);

    void updateData(MallProductTitle mallProductTitle);

    List<MallProductTitle> getList(Long productId, Integer platformType);

}
