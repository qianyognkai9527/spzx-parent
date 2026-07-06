package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.SysRoleService;
import com.joker.spzx.model.dto.system.SysRoleDto;
import com.joker.spzx.model.entity.system.SysRole;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * <p>
 * 角色 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@RestController
@Tag(description = "角色相关接口", name = "角色相关接口")
@RequestMapping("/admin/system/sysRole")
public class SysRoleController {

    @Autowired
    private SysRoleService sysRoleService;

    @Operation(summary = "分页查询")
    @PostMapping("/findByPage/{pageNum}/{pageSize}")
    public Result<IPage<SysRole>> findByPage(@RequestBody SysRoleDto sysRoleDto,
                                             @PathVariable(value = "pageNum") Integer pageNum,
                                             @PathVariable(value = "pageSize") Integer pageSize) {
        IPage<SysRole> pageInfo = sysRoleService.findByPage(sysRoleDto, pageNum, pageSize);
        return Result.build(pageInfo);
    }


    @Operation(summary = "所有角色")
    @GetMapping("/roleList/{userId}")
    public Result<Map<String, Object>> findByPage(@PathVariable Long userId) {
        Map<String, Object> pageInfo = sysRoleService.getList(userId);
        return Result.build(pageInfo);
    }

    @Operation(summary = "新增角色")
    @PostMapping("/saveSysRole")
    public Result<String> saveSysUser(@Valid @RequestBody SysRole sysRole) {
        sysRoleService.saveSysRole(sysRole);
        return Result.build(null);
    }

    @Operation(summary = "修改角色")
    @PostMapping("/updateSysRole")
    public Result<String> updateSysRole(@Valid @RequestBody SysRole sysRole) {
        sysRoleService.updateSysRole(sysRole);
        return Result.build(null);
    }

    @Operation(summary = "逻辑删除角色")
    @DeleteMapping("/deleteById/{id}")
    public Result<String> delete(@PathVariable Long id) {
        sysRoleService.deleteSysRole(id);
        return Result.build(null);
    }

}
