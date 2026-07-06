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
        LambdaQueryWrapper<MallOper> wrapper = lambdaQuery().getWrapper()
                .eq(MallOper::getType, brushPersonDto.getType());
        // 关键字搜索(简称或微信昵称)
        if (brushPersonDto.getKeyword() != null && !brushPersonDto.getKeyword().isEmpty()) {
            wrapper.and(w -> w.like(MallOper::getNickName, brushPersonDto.getKeyword())
                    .or().like(MallOper::getFullName, brushPersonDto.getKeyword())
                    .or().like(MallOper::getWxId, brushPersonDto.getKeyword()));
        }
        // 创建时间范围
        if (brushPersonDto.getCreateTime() != null) {
            wrapper.ge(MallOper::getCreateTime, brushPersonDto.getCreateTime());
        }
        if (brushPersonDto.getEndTime() != null) {
            wrapper.le(MallOper::getCreateTime, brushPersonDto.getEndTime());
        }
        // 刷单人员是通用的，不按平台过滤；买家秀人员可以按平台过滤
        if (brushPersonDto.getPlatformType() != null && brushPersonDto.getType() != null && brushPersonDto.getType() == 2) {
            wrapper.eq(MallOper::getPlatformType, brushPersonDto.getPlatformType());
        }
        page(page, wrapper);
        return page;
    }

    @Override
    public void saveData(MallOper mallOper) {
        mallOper.setCreateTime(LocalDateTime.now());
        mallOper.setCreateBy(AuthContextUtil.getUser().getId());
        // 刷手(type=1)默认通用，platform_type=0
        if (mallOper.getType() != null && mallOper.getType() == 1 && mallOper.getPlatformType() == null) {
            mallOper.setPlatformType(0);
        }
        mallOper.insert();
    }

    @Override
    public void updateData(MallOper mallOper) {
        mallOper.setUpdateBy(AuthContextUtil.getUser().getId());
        mallOper.setUpdateTime(LocalDateTime.now());
        mallOper.updateById();
    }

    @Override
    public void deleteById(Long id) {
        removeById(id);
    }

    @Override
    public List<MallOper> getAll(Integer type, Integer platformType) {
        LambdaQueryWrapper<MallOper> wrapper = lambdaQuery().getWrapper()
                .eq(Objects.nonNull(type), MallOper::getType, type);
        // 刷手是通用的，不按平台过滤
        return list(wrapper);
    }
}
