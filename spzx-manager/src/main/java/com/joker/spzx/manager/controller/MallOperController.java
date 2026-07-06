package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallOperService;
import com.joker.spzx.model.dto.mall.BrushPersonDto;
import com.joker.spzx.model.entity.oper.MallOper;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 电商资源 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@RestController
@Tag(name = "电商资源", description = "电商资源")
@RequestMapping("/admin/mall/brushPerson")
public class MallOperController {

    @Autowired
    private MallOperService mallOperService;

    @Operation(summary = "分页查询", description = "分页查询")
    @GetMapping("/findByPage/{pageNum}/{pageSize}")
    public Result<IPage<MallOper>> getPage(@PathVariable Integer pageNum,
                                           @PathVariable Integer pageSize, BrushPersonDto brushPersonDto) {
        IPage<MallOper> page = mallOperService.getPage(pageNum, pageSize, brushPersonDto);
        return Result.build(page);
    }

    @Operation(summary = "新增", description = "新增")
    @PostMapping("/saveBrushPerson")
    public Result<String> saveData(@RequestBody MallOper mallOper) {
        mallOperService.saveData(mallOper);
        return Result.build(null);
    }

    @Operation(summary = "修改", description = "修改")
    @PutMapping("/updateBrushPerson")
    public Result<String> updateData(@RequestBody MallOper mallOper) {
        mallOperService.updateData(mallOper);
        return Result.build(null);
    }

    @Operation(summary = "删除", description = "删除")
    @DeleteMapping("/deleteById/{id}")
    public Result<String> deleteById(@PathVariable Long id) {
        mallOperService.deleteById(id);
        return Result.build(null);
    }

    @Operation(summary = "查询所有人员", description = "查询所有人员(刷手或买家秀)")
    @GetMapping("/all")
    public Result<List<MallOper>> allData(@RequestParam(required = false) Integer type,
                                          @RequestParam(required = false) Integer platformType) {
        List<MallOper> page = mallOperService.getAll(type, platformType);
        return Result.build(page);
    }
}
