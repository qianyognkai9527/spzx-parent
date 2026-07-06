package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductMapper;
import com.joker.spzx.manager.service.MallProductService;
import com.joker.spzx.model.entity.oper.MallProduct;
import com.joker.spzx.model.entity.oper.MallProductTitle;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * <p>
 * 商品基本表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Service
public class MallProductServiceImpl extends ServiceImpl<MallProductMapper, MallProduct> implements MallProductService {

    @Override
    public IPage<MallProduct> pageList(Integer pageNum, Integer pageSize, Integer platformType, String keyword, String createTimeBegin, String createTimeEnd) {
        IPage<MallProduct> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<MallProduct> wrapper = new LambdaQueryWrapper<MallProduct>()
                .eq(MallProduct::getPlatformType, platformType)
                .like(StringUtils.isNotBlank(keyword), MallProduct::getTitle, keyword)
                .ge(StringUtils.isNotBlank(createTimeBegin), MallProduct::getCreateTime, createTimeBegin)
                .le(StringUtils.isNotBlank(createTimeEnd), MallProduct::getCreateTime, createTimeEnd)
                .orderByDesc(MallProduct::getCreateTime);
        return baseMapper.selectPage(page, wrapper);
    }

    @Override
    public void saveData(MallProduct mallProduct) {
        mallProduct.setCreateBy(AuthContextUtil.getUser().getId());
        mallProduct.setCreateTime(LocalDateTime.now());
        mallProduct.insert();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateData(MallProduct mallProduct) {
        Long operUserId = AuthContextUtil.getUser().getId();
        mallProduct.setUpdateBy(operUserId);
        MallProduct dbProduct = this.getById(mallProduct.getId());
        if (!StringUtils.equals(dbProduct.getTitle(), mallProduct.getTitle())) {
            MallProductTitle mallProductTitle = new MallProductTitle();
            mallProductTitle.setProductId(mallProduct.getId());
            mallProductTitle.setTitle(dbProduct.getTitle());
            mallProductTitle.setCreateBy(operUserId);
            mallProductTitle.setCreateTime(LocalDateTime.now());
            mallProductTitle.insert();
        }
        mallProduct.setUpdateTime(LocalDateTime.now());
        mallProduct.updateById();

    }
}
