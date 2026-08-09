package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.SkuBindService;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/skuBind")
public class SkuBindController {

    @Autowired
    private SkuBindService skuBindService;

    @GetMapping("/findByPage")
    public Result<Map<String, Object>> findByPage(@RequestParam(defaultValue = "1") Integer pageNum,
                                                   @RequestParam(defaultValue = "10") Integer pageSize,
                                                   @RequestParam(required = false) Integer platformType,
                                                   @RequestParam(required = false) Integer status) {
        List<Map<String, Object>> records = skuBindService.findBindList(pageNum, pageSize, platformType, status);
        long total = skuBindService.findBindCount(platformType, status);
        Map<String, Object> data = new HashMap<>();
        data.put("records", records);
        data.put("total", total);
        return Result.build(data);
    }

    @PutMapping("/confirm/{id}")
    public Result<String> confirm(@PathVariable Long id) {
        skuBindService.confirm(id);
        return Result.build(null);
    }

    @PutMapping("/mismatch/{id}")
    public Result<String> mismatch(@PathVariable Long id) {
        skuBindService.mismatch(id);
        return Result.build(null);
    }

    @PutMapping("/rebind/{id}/{sourceSkuId}")
    public Result<String> rebind(@PathVariable Long id, @PathVariable Long sourceSkuId) {
        skuBindService.rebind(id, sourceSkuId);
        return Result.build(null);
    }

    @GetMapping("/overview")
    public Result<Map<String, Object>> overview() {
        return Result.build(skuBindService.getOverview());
    }
}
