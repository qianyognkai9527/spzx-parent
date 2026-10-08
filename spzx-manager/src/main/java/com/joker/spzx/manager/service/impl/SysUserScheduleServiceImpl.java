package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.SysUserScheduleMapper;
import com.joker.spzx.manager.service.SysUserScheduleService;
import com.joker.spzx.model.dto.system.UserScheduleDtp;
import com.joker.spzx.model.entity.user.SysUserSchedule;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.commons.lang3.StringUtils;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * <p>
 * 每天日程安排表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-05-20 11:34:20
 */
@Service
public class SysUserScheduleServiceImpl extends ServiceImpl<SysUserScheduleMapper, SysUserSchedule> implements SysUserScheduleService {

    @Override
    public void saveData(SysUserSchedule sysUserSchedule) {
        Long userId = AuthContextUtil.getUser().getId();
        sysUserSchedule.setUserId(userId);
        sysUserSchedule.setCreateBy(userId);
        sysUserSchedule.setCreateTime(LocalDateTime.now());
        sysUserSchedule.setTaskCount(0);
        sysUserSchedule.setCompleteCount(0);
        sysUserSchedule.setStatus(0);
        this.baseMapper.insert(sysUserSchedule);

    }

    @Override
    public IPage<SysUserSchedule> pageList(UserScheduleDtp userScheduleDtp) {
        IPage<SysUserSchedule> page = userScheduleDtp.getPage();
        LambdaQueryWrapper<SysUserSchedule> eq = lambdaQuery().getWrapper()
                // 日期范围是闭区间：原来用 gt/lt 会把起止两天各自排除在外
                .ge(StringUtils.isNotBlank(userScheduleDtp.getDateStart()), SysUserSchedule::getDateStr, userScheduleDtp.getDateStart())
                .le(StringUtils.isNotBlank(userScheduleDtp.getDateEnd()), SysUserSchedule::getDateStr, userScheduleDtp.getDateEnd())
                .eq(SysUserSchedule::getUserId, AuthContextUtil.getUser().getId())
                // 不排序就按主键升序出，翻开的永远是最早那几天
                .orderByDesc(SysUserSchedule::getDateStr, SysUserSchedule::getId);
        page(page, eq);
        return page;
    }
}
