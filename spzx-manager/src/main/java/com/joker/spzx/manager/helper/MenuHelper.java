package com.joker.spzx.manager.helper;

import com.joker.spzx.model.entity.system.SysMenu;

import java.util.ArrayList;
import java.util.List;

public class MenuHelper {

    /**
     * 使用递归方法建菜单
     */
    public static List<SysMenu> buildTree(List<SysMenu> sysMenuList) {
        List<SysMenu> trees = new ArrayList<>();
        sysMenuList.forEach(sysMenu -> {
            if (sysMenu.getParentId().longValue() == 0) {
                trees.add(findChildren(sysMenu, sysMenuList));
            }
        });
        return trees;
    }

    /**
     * 递归查找子节点
     */
    public static SysMenu findChildren(SysMenu sysMenu, List<SysMenu> treeNodes) {
        sysMenu.setChildren(new ArrayList<>());
        treeNodes.forEach(treeNode -> {
            if (sysMenu.getId().longValue() == treeNode.getParentId().longValue()) {
                sysMenu.getChildren().add(findChildren(treeNode, treeNodes));
            }
        });
        return sysMenu;
    }
}
