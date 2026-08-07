package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.SourceFactoryService;
import com.joker.spzx.model.dto.product.SourceFactoryPageParam;
import com.joker.spzx.model.entity.product.SourceFactory;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * <p>
 * 爬虫工厂排行榜 前端控制器
 * </p>
 *
 * @author joker
 */
@Tag(name = "爬虫工厂排行榜")
@RestController
@RequestMapping("/admin/product/sourceFactory")
public class SourceFactoryController {

    private final SourceFactoryService sourceFactoryService;

    public SourceFactoryController(SourceFactoryService sourceFactoryService) {
        this.sourceFactoryService = sourceFactoryService;
    }

    @Operation(summary = "分页查询工厂排行榜")
    @GetMapping("/pageList")
    public Result<IPage<SourceFactory>> pageList(SourceFactoryPageParam pageParam) {
        IPage<SourceFactory> page = sourceFactoryService.pageList(pageParam);
        return Result.build(page);
    }

    @Operation(summary = "新增工厂")
    @PostMapping("/saveData")
    public Result<String> saveData(@RequestBody SourceFactory sourceFactory) {
        sourceFactoryService.saveData(sourceFactory);
        return Result.build("保存成功");
    }

    @Operation(summary = "修改工厂")
    @PutMapping("/updateData")
    public Result<String> updateData(@RequestBody SourceFactory sourceFactory) {
        sourceFactoryService.updateData(sourceFactory);
        return Result.build("修改成功");
    }

    @Operation(summary = "工厂详情")
    @GetMapping("/getDetail")
    public Result<SourceFactory> getDetail(@RequestParam Long id) {
        return Result.build(sourceFactoryService.getById(id));
    }

    @Operation(summary = "全量工厂列表(下拉用,按回头率降序)")
    @GetMapping("/allFactory")
    public Result<List<SourceFactory>> getAll(@RequestParam(required = false) Integer platformType) {
        return Result.build(sourceFactoryService.getAll(platformType));
    }

    @Operation(summary = "删除工厂(逻辑删除)")
    @DeleteMapping("/deleteById/{id}")
    public Result<String> deleteById(@PathVariable Long id) {
        sourceFactoryService.deleteById(id);
        return Result.build("删除成功");
    }
}
