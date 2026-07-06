package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.CategoryMapper;
import com.joker.spzx.manager.service.CategoryService;
import com.joker.spzx.model.entity.product.Category;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 商品分类 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class CategoryServiceImpl extends ServiceImpl<CategoryMapper, Category> implements CategoryService {

    @Override
    @Cacheable(cacheNames = "category:list", key = "#platformType + ':' + #parentId", unless = "#result == null || #result.isEmpty()")
    public List<Category> findByParentId(Long parentId, Integer platformType) {
        LambdaQueryWrapper<Category> wrapper = new LambdaQueryWrapper<Category>()
                .eq(Category::getPlatformType, platformType)
                .eq(Category::getParentId, parentId)
                .eq(Category::getIsDeleted, 0);
        List<Category> list = list(wrapper);
        if (CollectionUtils.isEmpty(list)) {
            return list;
        }
        List<Long> collect = list.stream().map(Category::getId).collect(Collectors.toList());
        List<Map<Long, Long>> idCountList = this.baseMapper.findCountByParentId(collect);
        Map<Long, Long> idCountMap = idCountList.stream().collect(Collectors.toMap(map -> map.get("parent_id"), map -> map.get("count")));

        list.stream().forEach(category -> {
            category.setHasChildren(idCountMap.containsKey(category.getId()));
        });
        return list;
    }
}
