package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.dto.mall.GenerateVariantDto;
import com.joker.spzx.model.dto.mall.RescoreDto;
import com.joker.spzx.model.vo.mall.VisualScoreSourceVo;
import com.joker.spzx.model.vo.mall.VisualScoreStatsVo;
import com.joker.spzx.model.vo.mall.VisualScoreVo;
import com.joker.spzx.model.vo.mall.VariantSetVo;

import java.util.List;

public interface VisualScoreService {

    IPage<VisualScoreVo> pageListPlatform(Integer pageNum, Integer pageSize, Integer platformType,
                                           String keyword, Integer scoreMin, Integer scoreMax);

    IPage<VisualScoreSourceVo> pageListSource(Integer pageNum, Integer pageSize,
                                               String keyword, Integer scoreMin, Integer scoreMax);

    VisualScoreStatsVo statsPlatform(Integer platformType);

    VisualScoreStatsVo statsSource();

    Integer rescore(RescoreDto dto);

    Integer generateVariant(GenerateVariantDto dto);

    List<VariantSetVo> variantList(Long productId, Integer platformType);
}
