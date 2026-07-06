package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.dto.mall.MallAddOrderPageDto;
import com.joker.spzx.model.dto.mall.MallAddOrderPageVo;
import com.joker.spzx.model.entity.oper.MallAddOrder;
import com.joker.spzx.model.vo.mall.BrushOrderStatVo;
import com.joker.spzx.model.vo.mall.BrushPersonStatVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * <p>
 * 补单表 Mapper 接口
 * </p>
 *
 * @author joker
 * @since 2025-06-10 14:05:10
 */
@Mapper
public interface MallAddOrderMapper extends BaseMapper<MallAddOrder> {

    IPage<MallAddOrderPageVo> selectAddOrderPage(@Param("page") IPage<MallAddOrderPageVo> page, @Param("mallAddOrderPageDto") MallAddOrderPageDto mallAddOrderPageDto);

    List<BrushPersonStatVo> selectBrushPersonStat(@Param("platformType") Integer platformType);

    List<BrushOrderStatVo> selectBrushOrderStat(@Param("platformType") Integer platformType, @Param("dimension") String dimension);
}
