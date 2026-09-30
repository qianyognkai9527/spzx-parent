package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.system.DictQueryDto;
import com.joker.spzx.model.entity.system.SysDictType;

/**
 * <p>
 * 字典类型表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
public interface SysDictTypeService extends IService<SysDictType> {

    IPage<SysDictType> getPage(Integer pageNum, Integer pageSize, DictQueryDto dictQueryDto);

    void saveData(SysDictType sysDictType);

    void updateData(SysDictType sysDictType);

    void removeData(Long id);

}
