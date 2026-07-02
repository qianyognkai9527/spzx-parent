package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallOperMapper;
import com.joker.spzx.manager.service.MallOperService;
import com.joker.spzx.model.dto.mall.BrushPersonDto;
import com.joker.spzx.model.entity.oper.MallOper;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

/**
 * <p>
 * 电商资源 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Service
public class MallOperServiceImpl extends ServiceImpl<MallOperMapper, MallOper> implements MallOperService {

    @Override
    public IPage<MallOper> getPage(Integer pageNum, Integer pageSize, BrushPersonDto brushPersonDto) {
        IPage<MallOper> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<MallOper> eq = lambdaQuery().getWrapper()
                .eq(brushPersonDto.getPlatformType() != null, MallOper::getPlatformType, brushPersonDto.getPlatformType())
                .eq(MallOper::getType, brushPersonDto.getType());
        page(page, eq);
        return page;
    }

    @Override
    public void saveData(MallOper mallOper) {
        mallOper.setCreateTime(LocalDateTime.now());
        mallOper.setCreateBy(AuthContextUtil.getUser().getId());
        mallOper.insert();
    }

    @Override
    public void updateData(MallOper mallOper) {
        mallOper.setUpdateBy(AuthContextUtil.getUser().getId());
        mallOper.setUpdateTime(LocalDateTime.now());
        mallOper.updateById();
    }

    @Override
    public List<MallOper> getAll(Integer type, Integer platformType) {
        LambdaQueryWrapper<MallOper> eq = lambdaQuery().getWrapper()
                .eq(MallOper::getPlatformType, platformType)
                .eq(Objects.nonNull(type), MallOper::getType, type);
        return list(eq);
    }
}
