package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.mall.EvalGapVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface EvalGapMapper {

    IPage<EvalGapVo> pageList(IPage<EvalGapVo> page,
                              @Param("platformType") Integer platformType,
                              @Param("keyword") String keyword);
}
