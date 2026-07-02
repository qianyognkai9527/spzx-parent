package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductTitleMapper;
import com.joker.spzx.manager.service.MallProductTitleService;
import com.joker.spzx.model.entity.oper.MallProductTitle;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 商品历史标题表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Service
public class MallProductTitleServiceImpl extends ServiceImpl<MallProductTitleMapper, MallProductTitle> implements MallProductTitleService {

    @Override
    public IPage<MallProductTitle> pageList(Integer pageNum, Integer pageSize) {
        IPage<MallProductTitle> page = new Page<>(pageNum, pageSize);
        page(page);
        return page;
    }

    @Override
    public void saveData(MallProductTitle mallProductTitle) {
        mallProductTitle.setCreateBy(AuthContextUtil.getUser().getId());
        mallProductTitle.setCreateTime(LocalDateTime.now());
        mallProductTitle.insert();
    }

    @Override
    public void updateData(MallProductTitle mallProductTitle) {
        mallProductTitle.setUpdateBy(AuthContextUtil.getUser().getId());
        mallProductTitle.setUpdateTime(LocalDateTime.now());
        mallProductTitle.updateById();
    }

    @Override
    public List<MallProductTitle> getList(Long productId, Integer platformType) {
        LambdaQueryWrapper<MallProductTitle> eq = lambdaQuery().getWrapper()
                .eq(MallProductTitle::getPlatformType, platformType)
                .eq(MallProductTitle::getProductId, productId)
                .orderByDesc(MallProductTitle::getCreateTime);
        return list(eq);
    }
}
