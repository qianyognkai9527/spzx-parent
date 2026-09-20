package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SysDictDataMapper;
import com.joker.spzx.manager.service.SysDictDataService;
import com.joker.spzx.model.entity.system.SysDictData;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 字典数据表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
@Service
public class SysDictDataServiceImpl extends ServiceImpl<SysDictDataMapper, SysDictData> implements SysDictDataService {

    @Override
    public List<SysDictData> getList(String dictType) {
        LambdaQueryWrapper<SysDictData> eq = lambdaQuery().getWrapper().eq(SysDictData::getDictType, dictType)
                .eq(SysDictData::getStatus, SysDictData.STATUS_NORMAL);


        return list(eq);
    }

    @Override
    public void saveData(SysDictData sysDictData) {
        sysDictData.setCreateBy(AuthContextUtil.getUser().getId());
        sysDictData.setCreateTime(LocalDateTime.now());

        sysDictData.insert();

    }

    @Override
    public void updateData(SysDictData sysDictData) {

        sysDictData.setUpdateBy(AuthContextUtil.getUser().getId());
        sysDictData.setUpdateTime(LocalDateTime.now());
        sysDictData.updateById();
    }
}
