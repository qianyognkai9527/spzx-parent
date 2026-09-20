package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SysDictTypeMapper;
import com.joker.spzx.manager.service.SysDictTypeService;
import com.joker.spzx.model.dto.system.DictQueryDto;
import com.joker.spzx.model.entity.system.SysDictType;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * <p>
 * 字典类型表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
@Service
public class SysDictTypeServiceImpl extends ServiceImpl<SysDictTypeMapper, SysDictType> implements SysDictTypeService {

    @Override
    public IPage<SysDictType> getPage(Integer pageNum, Integer pageSize, DictQueryDto dictQueryDto) {
        IPage<SysDictType> page = new Page<>(pageNum, pageSize);

        LambdaQueryWrapper<SysDictType> like = lambdaQuery().getWrapper().eq(SysDictType::getStatus, SysDictType.STATUS_NORMAL)
                .like(StringUtils.isNotBlank(dictQueryDto.getDictName()), SysDictType::getDictName, dictQueryDto.getDictName())
                .like(StringUtils.isNotBlank(dictQueryDto.getDictType()), SysDictType::getDictType, dictQueryDto.getDictType());
        page(page, like);

        return page;
    }

    @Override
    public void saveData(SysDictType sysDictType) {

        sysDictType.setCreateBy(AuthContextUtil.getUser().getId());
        sysDictType.setCreateTime(LocalDateTime.now());
        sysDictType.setStatus(SysDictType.STATUS_NORMAL);
        sysDictType.insert();

    }

    @Override
    public void updateData(SysDictType sysDictType) {
        sysDictType.setUpdateBy(AuthContextUtil.getUser().getId());
        sysDictType.setUpdateTime(LocalDateTime.now());
        sysDictType.updateById();
    }
}
