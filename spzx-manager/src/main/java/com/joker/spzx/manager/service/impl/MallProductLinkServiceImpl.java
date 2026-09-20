package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.util.PageQueryUtil;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductLinkMapper;
import com.joker.spzx.manager.service.MallProductLinkService;
import com.joker.spzx.model.entity.oper.MallProductLink;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * <p>
 * 商品和货源关系表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Service
public class MallProductLinkServiceImpl extends ServiceImpl<MallProductLinkMapper, MallProductLink> implements MallProductLinkService {

    @Override
    public IPage<MallProductLink> pageList(Integer pageNum, Integer pageSize, Integer platformType) {
        LambdaQueryWrapper<MallProductLink> wrapper = new LambdaQueryWrapper<MallProductLink>()
                .eq(MallProductLink::getPlatformType, platformType);
        return PageQueryUtil.page(this, pageNum, pageSize, wrapper);
    }

    @Override
    public void saveData(MallProductLink mallProductLink) {
        mallProductLink.setCreateBy(AuthContextUtil.getUser().getId());
        mallProductLink.setCreateTime(LocalDateTime.now());
        mallProductLink.insert();
    }

    @Override
    public void updateData(MallProductLink mallProductLink) {
        mallProductLink.setUpdateBy(AuthContextUtil.getUser().getId());
        mallProductLink.setUpdateTime(LocalDateTime.now());
        mallProductLink.updateById();
    }
}
