package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.util.PageQueryUtil;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.mapper.SysDictDataMapper;
import com.joker.spzx.manager.mapper.SysDictTypeMapper;
import com.joker.spzx.manager.service.SysDictTypeService;
import com.joker.spzx.model.dto.system.DictQueryDto;
import com.joker.spzx.model.entity.system.SysDictData;
import com.joker.spzx.model.entity.system.SysDictType;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
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

    @Autowired
    private SysDictDataMapper sysDictDataMapper;

    @Override
    public IPage<SysDictType> getPage(Integer pageNum, Integer pageSize, DictQueryDto dictQueryDto) {
        LambdaQueryWrapper<SysDictType> like = lambdaQuery().getWrapper().eq(SysDictType::getStatus, SysDictType.STATUS_NORMAL)
                .like(StringUtils.isNotBlank(dictQueryDto.getDictName()), SysDictType::getDictName, dictQueryDto.getDictName())
                .like(StringUtils.isNotBlank(dictQueryDto.getDictType()), SysDictType::getDictType, dictQueryDto.getDictType());
        return PageQueryUtil.page(this, pageNum, pageSize, like);
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

    @Override
    public void removeData(Long id) {
        SysDictType type = getById(id);
        if (type == null) {
            return; // 已经没了，按幂等删除处理
        }
        Long used = sysDictDataMapper.selectCount(Wrappers.<SysDictData>lambdaQuery()
                .eq(SysDictData::getDictType, type.getDictType()));
        if (used != null && used > 0) {
            throw new ServiceException(204, "字典类型「" + type.getDictType() + "」下还有 " + used + " 个字典值，请先删除字典值");
        }
        removeById(id);
    }
}
