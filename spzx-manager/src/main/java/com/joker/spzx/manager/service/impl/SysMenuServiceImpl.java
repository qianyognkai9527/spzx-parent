package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.google.common.collect.Lists;
import com.joker.spzx.manager.helper.MenuHelper;
import com.joker.spzx.manager.mapper.SysMenuMapper;
import com.joker.spzx.manager.mapper.SysRoleMenuMapper;
import com.joker.spzx.manager.service.SysMenuService;
import com.joker.spzx.model.entity.system.SysMenu;
import com.joker.spzx.model.entity.system.SysRoleMenu;
import com.joker.spzx.model.vo.system.SysMenuVo;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

/**
 * <p>
 * 菜单表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class SysMenuServiceImpl extends ServiceImpl<SysMenuMapper, SysMenu> implements SysMenuService {


    private final SysRoleMenuMapper sysRoleMenuMapper;

    public SysMenuServiceImpl(SysRoleMenuMapper sysRoleMenuMapper) {
        this.sysRoleMenuMapper = sysRoleMenuMapper;
    }

    @Override
    @Cacheable(cacheNames = "menu:tree", key = "'tree'", unless = "#result == null || #result.isEmpty()")
    public List<SysMenu> getTreeNodes() {
        LambdaQueryWrapper<SysMenu> eq = lambdaQuery().getWrapper().eq(SysMenu::getIsDeleted, 0)
                .orderByAsc(SysMenu::getSortValue);
        List<SysMenu> list = list(eq);
        if (CollectionUtils.isEmpty(list)) {
            return list;
        }
        List<SysMenu> sysMenus = MenuHelper.buildTree(list);
        return sysMenus;
    }

    @Override
    @CacheEvict(cacheNames = "menu:tree", allEntries = true)
    public void saveData(SysMenu sysMenu) {
        sysMenu.setIsDeleted(0);
        sysMenu.setCreateTime(LocalDateTime.now());
        sysMenu.insert();

        updateSysRoleMenuIsHalf(sysMenu);
    }

    private void updateSysRoleMenuIsHalf(SysMenu sysMenu) {
        LambdaQueryWrapper<SysMenu> eq = lambdaQuery().getWrapper().eq(SysMenu::getParentId, sysMenu.getParentId())
                .eq(SysMenu::getIsDeleted, 0)
                .last(" limit 1");
        SysMenu one = this.getOne(eq);
        if (Objects.isNull(one)) {
            LambdaQueryWrapper<SysRoleMenu> eq1 = new LambdaQueryWrapper<SysRoleMenu>()
                    .eq(SysRoleMenu::getMenuId, one.getId())
                    .eq(SysRoleMenu::getIsDeleted, 0)
                    .eq(SysRoleMenu::getIsHalf, 0);
            sysRoleMenuMapper.update(new SysRoleMenu() {{
                setIsHalf(1);
            }}, eq1);
            updateSysRoleMenuIsHalf(one);
        }
    }

    @Override
    @CacheEvict(cacheNames = "menu:tree", allEntries = true)
    public void updateData(SysMenu sysMenu) {
        sysMenu.setUpdateTime(LocalDateTime.now());
        sysMenu.updateById();
    }

    @Override
    @CacheEvict(cacheNames = "menu:tree", allEntries = true)
    public void deleteData(Long id) {
        SysMenu sysMenu = new SysMenu() {{
            setId(id);
            setIsDeleted(1);
        }};
        sysMenu.updateById();
    }

    @Override
    public List<SysMenuVo> findUserMenuList() {
        Long userId = AuthContextUtil.getUser().getId();
        List<SysMenu> menus = this.baseMapper.selectListByUserId(userId);
        List<SysMenu> sysMenus = MenuHelper.buildTree(menus);
        return this.buildMenus(sysMenus);


    }

    private List<SysMenuVo> buildMenus(List<SysMenu> sysMenus) {
        List<SysMenuVo> sysMenuVoList = Lists.newLinkedList();
        sysMenus.stream().forEach(sysMenu -> {
            SysMenuVo sysMenuVo = new SysMenuVo() {{
                setTitle(sysMenu.getTitle());
                setName(sysMenu.getComponent());
                if (!CollectionUtils.isEmpty(sysMenu.getChildren())) {
                    setChildren(buildMenus(sysMenu.getChildren()));
                }
            }};
            sysMenuVoList.add(sysMenuVo);
        });

        return sysMenuVoList;
    }
}
