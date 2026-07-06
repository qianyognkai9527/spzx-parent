package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.mall.BrushPersonDto;
import com.joker.spzx.model.entity.oper.MallOper;

import java.util.List;

/**
 * <p>
 * 电商资源 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
public interface MallOperService extends IService<MallOper> {

    IPage<MallOper> getPage(Integer pageNum, Integer pageSize, BrushPersonDto brushPersonDto);

    void saveData(MallOper mallOper);

    void updateData(MallOper mallOper);

    void deleteById(Long id);

    List<MallOper> getAll(Integer type, Integer platformType);
}
