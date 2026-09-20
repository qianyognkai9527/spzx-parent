package com.joker.spzx.manager.service.impl;

import com.joker.spzx.manager.util.PageQueryUtil;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.google.common.collect.Maps;
import com.joker.spzx.manager.mapper.SysRoleMapper;
import com.joker.spzx.manager.mapper.SysUserRoleMapper;
import com.joker.spzx.manager.service.SysRoleService;
import com.joker.spzx.model.dto.system.SysRoleDto;
import com.joker.spzx.model.entity.system.SysRole;
import com.joker.spzx.model.entity.system.SysRoleUser;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * <p>
 * 角色 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class SysRoleServiceImpl extends ServiceImpl<SysRoleMapper, SysRole> implements SysRoleService {


    @Autowired
    private SysUserRoleMapper sysUserRoleMapper;

    @Override
    public IPage<SysRole> findByPage(SysRoleDto sysRoleDto, Integer pageNum, Integer pageSize) {
        LambdaQueryWrapper<SysRole> eq = lambdaQuery().getWrapper().like(StringUtils.isNotBlank(sysRoleDto.getRoleName()), SysRole::getRoleName, sysRoleDto.getRoleName())
                .eq(SysRole::getIsDeleted, 0);
        return PageQueryUtil.page(this, pageNum, pageSize, eq);
    }

    @Override
    public void saveSysRole(SysRole sysRole) {
        sysRole.setIsDeleted(0);
        this.save(sysRole);
    }

    @Override
    public void updateSysRole(SysRole sysRole) {
        this.updateById(sysRole);
    }

    @Override
    public void deleteSysRole(Long id) {
        SysRole sysRole = new SysRole() {{
            setId(id);
            setIsDeleted(1);
        }};
        this.updateById(sysRole);
    }

    @Override
    public Map<String, Object> getList(Long sysRoleDto) {
        Map<String, Object> map = Maps.newHashMap();
        LambdaQueryWrapper<SysRole> eq = lambdaQuery().getWrapper().eq(SysRole::getIsDeleted, 0);
        List<SysRole> list = list(eq);
        map.put("allRolesList", list);
        LambdaQueryWrapper<SysRoleUser> lambdaQueryWrapper = new LambdaQueryWrapper<SysRoleUser>().eq(SysRoleUser::getUserId, sysRoleDto);
        List<SysRoleUser> sysRoleUsers = sysUserRoleMapper.selectList(lambdaQueryWrapper);
        List<Long> sysRoleUserIds = sysRoleUsers.stream().map(SysRoleUser::getRoleId).collect(Collectors.toList());

        map.put("sysUserRoles", sysRoleUserIds);
        return map;
    }
}
