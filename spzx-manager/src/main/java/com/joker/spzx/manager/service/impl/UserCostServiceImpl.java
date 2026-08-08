package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.UserCostMapper;
import com.joker.spzx.manager.service.UserCostService;
import com.joker.spzx.model.dto.product.UserCostDto;
import com.joker.spzx.model.dto.product.UserCostPageDto;
import com.joker.spzx.model.entity.user.UserCost;
import com.joker.spzx.model.vo.product.UserCostDetailVo;
import com.joker.spzx.model.vo.product.UserCostPageVo;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * <p>
 * 商品规格 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-08-25 16:12:25
 */
@Service
public class UserCostServiceImpl extends ServiceImpl<UserCostMapper, UserCost> implements UserCostService {

    @Override
    public IPage<UserCostPageVo> findByPage(UserCostPageDto userCostQueryDto) {
        IPage<UserCostPageVo> page = userCostQueryDto.getPage();
        this.baseMapper.selectPageList(page, userCostQueryDto);
        return page;
    }

    @Override
    public UserCostDetailVo getDetail(Long id) {
        UserCost userCost = this.getById(id);
        if (userCost == null) {
            return null;
        }
        UserCostDetailVo vo = new UserCostDetailVo();
        BeanUtils.copyProperties(userCost, vo);
        return vo;
    }

    @Override
    public void saveData(UserCostDto userCostDto) {

        UserCost userCost = new UserCost();
        BeanUtils.copyProperties(userCostDto, userCost);
        Long id = AuthContextUtil.getUser().getId();
        userCost.setUserId(id);
        userCost.setCreateBy(id);
        userCost.setCreateTime(LocalDateTime.now());
        userCost.setIsDeleted(0);
        userCost.insert();

    }

    @Override
    public void updateData(UserCostDto userCostDto) {
        UserCost userCost = new UserCost();
        BeanUtils.copyProperties(userCostDto, userCost);
        Long id = AuthContextUtil.getUser().getId();
        userCost.setUserId(id);
        userCost.setUpdateBy(id);
        userCost.setUpdateTime(LocalDateTime.now());
        userCost.updateById();
    }

    @Override
    public void removeData(Long id) {
        UserCost userCost = new UserCost();
        userCost.setId(id);
        userCost.setIsDeleted(1);
        userCost.setUpdateBy(AuthContextUtil.getUser().getId());
        userCost.setUpdateTime(LocalDateTime.now());
        userCost.updateById();
    }
}
