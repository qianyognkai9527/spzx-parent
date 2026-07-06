package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductFactoryMapper;
import com.joker.spzx.manager.service.MallProductFactoryService;
import com.joker.spzx.model.dto.product.ProductFactoryPageParam;
import com.joker.spzx.model.entity.oper.MallProductFactory;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 工厂基本信息表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Service
public class MallProductFactoryServiceImpl extends ServiceImpl<MallProductFactoryMapper, MallProductFactory> implements MallProductFactoryService {

    @Override
    public IPage<MallProductFactory> pageList(ProductFactoryPageParam pageParam) {
        IPage<MallProductFactory> objectPage = pageParam.getPage();
        LambdaQueryWrapper<MallProductFactory> wrapper = lambdaQuery().getWrapper()
                .eq(pageParam.getPlatformType() != null, MallProductFactory::getPlatformType, pageParam.getPlatformType())
                .like(StringUtils.isNotBlank(pageParam.getFactoryName()), MallProductFactory::getFactoryName, pageParam.getFactoryName());
        page(objectPage, wrapper);
        return objectPage;
    }

    @Override
    public void saveData(MallProductFactory mallProductFactory) {
        mallProductFactory.setCreateBy(AuthContextUtil.getUser().getId());
        mallProductFactory.setCreateTime(LocalDateTime.now());
        mallProductFactory.insert();
    }

    @Override
    public void updateData(MallProductFactory mallProductFactory) {
        mallProductFactory.setUpdateBy(AuthContextUtil.getUser().getId());
        mallProductFactory.setUpdateTime(LocalDateTime.now());
        mallProductFactory.updateById();
    }

    @Override
    public List<MallProductFactory> getAllProductFactory(Integer platformType) {
        LambdaQueryWrapper<MallProductFactory> queryWrapper = lambdaQuery().getWrapper()
                .eq(platformType != null, MallProductFactory::getPlatformType, platformType)
                .orderByDesc(MallProductFactory::getDeployCount);
        return list(queryWrapper);
    }

    @Override
    public void deleteById(Long id) {
        MallProductFactory factory = getById(id);
        if (factory != null) {
            factory.setUpdateBy(AuthContextUtil.getUser().getId());
            factory.setUpdateTime(LocalDateTime.now());
            removeById(id);
        }
    }
}
