package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.mall.MallAddOrderPageDto;
import com.joker.spzx.model.dto.mall.MallAddOrderPageVo;
import com.joker.spzx.model.entity.oper.MallAddOrder;
import com.joker.spzx.model.vo.mall.BrushOrderStatVo;
import com.joker.spzx.model.vo.mall.BrushPersonStatVo;

import java.util.List;

/**
 * <p>
 * 补单表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-06-10 14:05:10
 */
public interface MallAddOrderService extends IService<MallAddOrder> {

    IPage<MallAddOrderPageVo> findByPage(MallAddOrderPageDto mallAddOrderPageDto);

    void insertData(MallAddOrder mallAddOrder);

    void updateData(MallAddOrder mallAddOrder);

    void deleteById(Long id);

    void settleCommission(List<Long> idList);

    List<BrushPersonStatVo> getBrushPersonStat(Integer platformType);

    List<BrushOrderStatVo> getBrushOrderStat(Integer platformType, String dimension);
}
