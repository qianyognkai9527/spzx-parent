package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.inventory.SkuBindRelation;

import java.util.List;
import java.util.Map;

public interface SkuBindService extends IService<SkuBindRelation> {

    List<Map<String, Object>> findBindList(Integer pageNum, Integer pageSize, Integer platformType, Integer status);

    long findBindCount(Integer platformType, Integer status);

    Map<String, Object> getOverview();

    boolean confirm(Long id);

    boolean mismatch(Long id);

    boolean rebind(Long id, Long sourceSkuId);
}
