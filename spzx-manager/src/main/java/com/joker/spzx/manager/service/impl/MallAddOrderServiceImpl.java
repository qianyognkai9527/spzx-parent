package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallAddOrderMapper;
import com.joker.spzx.manager.service.MallAddOrderService;
import com.joker.spzx.model.dto.mall.MallAddOrderPageDto;
import com.joker.spzx.model.dto.mall.MallAddOrderPageVo;
import com.joker.spzx.model.entity.oper.MallAddOrder;
import com.joker.spzx.model.vo.mall.BrushPersonStatVo;
import com.joker.spzx.model.vo.mall.BrushOrderStatVo;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * <p>
 * 补单表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-06-10 14:05:10
 */
@Service
public class MallAddOrderServiceImpl extends ServiceImpl<MallAddOrderMapper, MallAddOrder> implements MallAddOrderService {

    @Override
    public IPage<MallAddOrderPageVo> findByPage(MallAddOrderPageDto mallAddOrderPageDto) {
        IPage<MallAddOrderPageVo> page = mallAddOrderPageDto.getPage();
        this.baseMapper.selectAddOrderPage(page, mallAddOrderPageDto);
        return page;
    }

    @Override
    public void insertData(MallAddOrder mallAddOrder) {
        mallAddOrder.setCreateBy(AuthContextUtil.getUser().getId());
        mallAddOrder.setCreateTime(LocalDateTime.now());
        if (mallAddOrder.getHireIsPay() == null) {
            mallAddOrder.setHireIsPay(0);
        }
        if (mallAddOrder.getSeedIsPay() == null) {
            mallAddOrder.setSeedIsPay(0);
        }
        mallAddOrder.insert();
    }

    @Override
    public void updateData(MallAddOrder mallAddOrder) {
        mallAddOrder.setUpdateBy(AuthContextUtil.getUser().getId());
        mallAddOrder.setUpdateTime(LocalDateTime.now());
        mallAddOrder.updateById();
    }

    @Override
    public void deleteById(Long id) {
        removeById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void settleCommission(List<Long> idList) {
        if (idList == null || idList.isEmpty()) {
            return;
        }
        LocalDateTime now = LocalDateTime.now();
        // 单条条件 UPDATE 完成结算：消除循环读写与"读-改-写"竞态
        this.update(new com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<MallAddOrder>()
                .set(MallAddOrder::getHireIsPay, 1)
                .set(MallAddOrder::getSettlementTime, now)
                .set(MallAddOrder::getUpdateBy, AuthContextUtil.getUser().getId())
                .set(MallAddOrder::getUpdateTime, now)
                .in(MallAddOrder::getId, idList)
                .eq(MallAddOrder::getHireIsPay, 0));
    }

    @Override
    public List<BrushPersonStatVo> getBrushPersonStat(Integer platformType) {
        return this.baseMapper.selectBrushPersonStat(platformType);
    }

    @Override
    public List<BrushOrderStatVo> getBrushOrderStat(Integer platformType, String dimension) {
        return this.baseMapper.selectBrushOrderStat(platformType, dimension);
    }
}
