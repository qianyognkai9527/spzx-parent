package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.mall.VisualScoreImgVo;
import com.joker.spzx.model.vo.mall.VisualScoreSourceVo;
import com.joker.spzx.model.vo.mall.VisualScoreStatsVo;
import com.joker.spzx.model.vo.mall.VisualScoreVo;
import com.joker.spzx.model.vo.mall.VariantItemVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface VisualScoreMapper {

    IPage<VisualScoreVo> pageListPlatform(IPage<VisualScoreVo> page,
                                          @Param("platformType") Integer platformType,
                                          @Param("keyword") String keyword,
                                          @Param("scoreMin") Integer scoreMin,
                                          @Param("scoreMax") Integer scoreMax);

    List<VisualScoreImgVo> selectImgs(@Param("productIds") List<Long> productIds,
                                      @Param("platformType") Integer platformType);

    IPage<VisualScoreSourceVo> pageListSource(IPage<VisualScoreSourceVo> page,
                                               @Param("keyword") String keyword,
                                               @Param("scoreMin") Integer scoreMin,
                                               @Param("scoreMax") Integer scoreMax);

    VisualScoreStatsVo statsPlatform(@Param("platformType") Integer platformType);

    VisualScoreStatsVo statsSource();

    List<VariantItemVo> selectVariants(@Param("productId") Long productId,
                                       @Param("platformType") Integer platformType);
}
