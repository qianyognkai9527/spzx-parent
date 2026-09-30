package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.platform.ShopService;
import com.joker.spzx.model.entity.platform.Shop;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 店铺维护：采集通道、CDP 端口、默认店铺、启停。
 * 只读注册表在 PlatformController#shopList，那份对外隐去了 credential_ref 与 cdp_port。
 */
@RestController
@Tag(name = "店铺维护", description = "店铺注册表的增删改查")
@RequestMapping("/admin/shop")
public class ShopController {

    @Autowired
    private ShopService shopService;

    @Operation(summary = "店铺列表（含停用与内部字段，供维护页使用）")
    @GetMapping("/list")
    public Result<List<Shop>> list(@RequestParam(required = false) Integer platform) {
        return Result.build(shopService.listForManage(platform));
    }

    @Operation(summary = "引用计数（删除前确认用）")
    @GetMapping("/usage/{id}")
    public Result<Map<String, Long>> usage(@PathVariable Long id) {
        return Result.build(shopService.usage(id));
    }

    @PostMapping
    public Result<Void> create(@RequestBody Shop shop) {
        String err = shopService.validate(shop);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = shopService.nameConflict(shop.getShopName(), shop.getPlatformCode(), null);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        shop.setId(null);
        if (shop.getIngestChannel() == null || shop.getIngestChannel().isBlank()) {
            shop.setIngestChannel("browser");
        }
        if (shop.getIsDefault() == null) {
            shop.setIsDefault(0);
        }
        if (shop.getStatus() == null) {
            shop.setStatus(1);
        }
        shopService.applyDefaultExclusive(shop);
        shopService.saveShop(shop);
        return Result.build(null);
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Shop shop) {
        Shop row = shopService.getById(id);
        if (row == null) {
            return Result.build(null, 204, "店铺不存在");
        }
        ShopService.mergeEditable(row, shop);
        String err = shopService.validate(row);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = shopService.nameConflict(row.getShopName(), row.getPlatformCode(), id);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        shopService.applyDefaultExclusive(row);
        shopService.updateShop(row);
        return Result.build(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        if (shopService.getById(id) == null) {
            return Result.build(null, 204, "店铺不存在");
        }
        long used = shopService.totalUsage(id);
        if (used > 0) {
            return Result.build(null, 204, "该店铺已被 " + used + " 条平台商品/订单/售后/提醒引用，无法删除；可改为停用");
        }
        shopService.removeShop(id);
        return Result.build(null);
    }
}
