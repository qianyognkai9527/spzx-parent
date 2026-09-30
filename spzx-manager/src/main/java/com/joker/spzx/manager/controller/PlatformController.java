package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.platform.PlatformRegistryService;
import com.joker.spzx.model.entity.platform.Platform;
import com.joker.spzx.model.entity.platform.Shop;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 平台注册表控制器：平台、店铺、能力矩阵的只读接口
 */
@RestController
@Tag(name = "平台注册表", description = "平台/店铺/能力查询接口")
@RequestMapping("/admin/platform")
public class PlatformController {

    @Autowired
    private PlatformRegistryService platformRegistryService;

    @Operation(summary = "平台列表（含停用）")
    @GetMapping("/list")
    public Result<List<Platform>> list() {
        return Result.build(platformRegistryService.listAll());
    }

    @Operation(summary = "启用中的平台列表")
    @GetMapping("/enabled")
    public Result<List<Platform>> enabled() {
        return Result.build(platformRegistryService.listEnabled());
    }

    @Operation(summary = "启用中的店铺列表，platform 为空则返回全部平台")
    @GetMapping("/shop/list")
    public Result<List<Shop>> shopList(@RequestParam(required = false) Integer platform) {
        return Result.build(platformRegistryService.listShops(platform));
    }

    @Operation(summary = "指定平台的能力矩阵")
    @GetMapping("/capability")
    public Result<Map<String, Boolean>> capability(@RequestParam Integer platform) {
        return Result.build(platformRegistryService.capabilities(platform));
    }
}
