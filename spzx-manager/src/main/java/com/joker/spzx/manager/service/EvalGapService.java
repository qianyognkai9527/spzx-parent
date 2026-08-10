package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.mall.EvalGapVo;

public interface EvalGapService {

    IPage<EvalGapVo> pageList(Integer pageNum, Integer pageSize, Integer platformType, String keyword);
}
