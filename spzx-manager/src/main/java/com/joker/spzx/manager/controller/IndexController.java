package com.joker.spzx.manager.controller;


import com.joker.spzx.manager.service.SysMenuService;
import com.joker.spzx.manager.service.SysUserService;
import com.joker.spzx.model.dto.system.LoginDto;
import com.joker.spzx.model.entity.system.SysUser;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.system.LoginVo;
import com.joker.spzx.model.vo.system.SysMenuVo;
import com.joker.spzx.model.vo.system.ValidateCodeVo;
import com.joker.spzx.utils.AuthContextUtil;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "用户接口")
@RestController
@RequestMapping("/admin/system/index")
public class IndexController {

    @Autowired
    private SysUserService sysUserService;

    @Autowired
    private SysMenuService sysMenuService;

    @PostMapping("/login")
    @Operation(summary = "用户登录")
    public Result<LoginVo> login(@Valid @RequestBody LoginDto loginDto) {
        LoginVo loginVo = sysUserService.login(loginDto);
        return Result.build(loginVo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/genVarifyCode")
    @Operation(summary = "生成验证码")
    private Result<ValidateCodeVo> genVarifyCode() {
        ValidateCodeVo validateCodeVo = sysUserService.genVarifyCode();
        return Result.build(validateCodeVo, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/getUserInfo")
    @Operation(summary = "获取用户信息")
    private Result<SysUser> getUserInfo(@RequestHeader(name = "token") String token) {
        SysUser sysUser = AuthContextUtil.getUser();
        return Result.build(sysUser, ResultCodeEnum.SUCCESS);
    }

    @GetMapping("/logout")
    @Operation(summary = "用户退出")
    private Result<SysUser> logout(@RequestHeader(name = "token") String token) {
        sysUserService.logout(token);
        return Result.build(null);
    }


    @GetMapping("/menus")
    @Operation(summary = "动态菜单")
    private Result<List<SysMenuVo>> getMenus() {
        List<SysMenuVo> validateCodeVo = sysMenuService.findUserMenuList();
        return Result.build(validateCodeVo, ResultCodeEnum.SUCCESS);
    }

}
