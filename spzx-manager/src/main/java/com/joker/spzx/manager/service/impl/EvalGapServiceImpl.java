package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.util.PageQueryUtil;
import com.joker.spzx.manager.mapper.EvalGapMapper;
import com.joker.spzx.manager.service.EvalGapService;
import com.joker.spzx.model.vo.mall.EvalGapVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class EvalGapServiceImpl implements EvalGapService {

    @Autowired
    private EvalGapMapper evalGapMapper;

    @Override
    public IPage<EvalGapVo> pageList(Integer pageNum, Integer pageSize, Integer platformType, String keyword) {
        Page<EvalGapVo> page = PageQueryUtil.of(pageNum, pageSize);
        return evalGapMapper.pageList(page, platformType, keyword);
    }
}
