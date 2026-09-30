package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.SysDictDataService;
import com.joker.spzx.model.entity.system.SysDictData;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 字典数据表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
@RestController
@RequestMapping("/admin/dictData")
public class SysDictDataController {

    private final SysDictDataService sysDictDataService;

    public SysDictDataController(SysDictDataService sysDictDataService) {
        this.sysDictDataService = sysDictDataService;
    }

    @GetMapping("/getList/{dictType}")
    public Result<List<SysDictData>> getList(@PathVariable String dictType) {
        List<SysDictData> data = sysDictDataService.getList(dictType);
        return Result.build(data);
    }

    @PostMapping("/insert")
    public Result<String> daveData(@RequestBody SysDictData sysDictData) {
        sysDictDataService.saveData(sysDictData);
        return Result.build(null);
    }

    @PostMapping("/update")
    public Result<String> updateData(@RequestBody SysDictData sysDictData) {
        sysDictDataService.updateData(sysDictData);
        return Result.build(null);
    }

    @DeleteMapping("/delete/{id}")
    public Result<String> deleteData(@PathVariable Long id) {
        sysDictDataService.removeById(id);
        return Result.build(null);
    }

}
