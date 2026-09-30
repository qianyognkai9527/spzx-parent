package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.SysDictTypeService;
import com.joker.spzx.model.dto.system.DictQueryDto;
import com.joker.spzx.model.entity.system.SysDictType;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * <p>
 * 字典类型表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
@RestController
@RequestMapping("/admin/system/dictType")
public class SysDictTypeController {

    @Autowired
    private SysDictTypeService sysDictTypeService;

    @GetMapping("/page/{pageNum}/{pageSize}")
    public Result<IPage<SysDictType>> findByPage(@PathVariable Integer pageNum, @PathVariable Integer pageSize, DictQueryDto dictQueryDto) {
        IPage<SysDictType> page = sysDictTypeService.getPage(pageNum, pageSize, dictQueryDto);
        return Result.build(page);
    }

    @PostMapping("/insert")
    public Result<String> insertData(@RequestBody SysDictType sysDictType) {
        sysDictTypeService.saveData(sysDictType);
        return Result.build(null);
    }

    @PutMapping("/update")
    public Result<String> updateData(@RequestBody SysDictType sysDictType) {
        sysDictTypeService.updateData(sysDictType);
        return Result.build(null);
    }

    @DeleteMapping("/removeById/{id}")
    public Result<String> removeData(@PathVariable Long id) {
        sysDictTypeService.removeData(id);
        return Result.build(null);
    }

}
