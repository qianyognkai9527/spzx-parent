package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.product.Category;

import java.util.List;

/**
 * <p>
 * 商品分类 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
public interface CategoryService extends IService<Category> {

    List<Category> findByParentId(Long parentId, Integer platformType);
}
