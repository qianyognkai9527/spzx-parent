package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.SysUserService;
import com.joker.spzx.model.dto.system.AssginRoleDto;
import com.joker.spzx.model.dto.system.SysUserDto;
import com.joker.spzx.model.entity.system.SysUser;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.common.annotation.Log;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

/**
 * <p>
 * 用户表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Tag(name = "用户接口", description = "用户接口")
@RestController
@RequestMapping(value = "/admin/system/sysUser")
public class SysUserController {

    private final SysUserService sysUserService;

    public SysUserController(SysUserService sysUserService) {
        this.sysUserService = sysUserService;
    }

    @PostMapping("/findByPage/{pageNum}/{pageSize}")
    @Operation(summary = "分页查询")
    public Result<IPage<SysUser>> findByPage(@RequestBody SysUserDto sysUserDto,
                                             @PathVariable Integer pageNum,
                                             @PathVariable Integer pageSize) {
        IPage<SysUser> page = sysUserService.findByPage(sysUserDto, pageNum, pageSize);
        return Result.build(page);
    }

    @PostMapping("/saveSysUser")
    @Log(title = "用户管理", businessType = 1)
    @Operation(summary = "分页查询")
    public Result<IPage<SysUser>> saveSysUser(@RequestBody SysUser sysUser) {
        sysUserService.saveSysUser(sysUser);
        return Result.build(null);
    }

    @PostMapping("/updateSysUser")
    @Log(title = "用户管理", businessType = 2)
    @Operation(summary = "分页查询")
    public Result<IPage<SysUser>> updateSysUser(@RequestBody SysUser sysUser) {
        sysUserService.updateSysUser(sysUser);
        return Result.build(null);
    }

    @DeleteMapping("/deleteById/{id}")
    @Log(title = "用户管理", businessType = 3)
    @Operation(summary = "分页查询")
    public Result<IPage<SysUser>> delete(@PathVariable Long id) {
        sysUserService.deleteSysUser(id);
        return Result.build(null);
    }

    @PostMapping("/doAssgin")
    @Log(title = "用户角色分配", businessType = 2)
    @Operation(summary = "分配角色")
    public Result<String> assignRole(@RequestBody @Validated AssginRoleDto assginRoleDto) {
        sysUserService.assignRole(assginRoleDto);
        return Result.build(null);
    }
}
