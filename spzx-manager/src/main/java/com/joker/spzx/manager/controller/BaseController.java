package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 通用 CRUD 基类控制器
 * 子类继承后自动拥有标准 /list /get/{id} /save /update /delete/{id} 端点,
 * 子类用 @RequestMapping 指定路径 + 按需覆盖或追加自定义端点。
 * 老控制器路径各异, 不强制迁移, 仅新控制器(如订单模块)复用。
 *
 * @author joker
 */
public abstract class BaseController<S extends IService<T>, T> {

    @Autowired
    protected S service;

    @GetMapping("/list")
    public Result<List<T>> list() {
        return Result.build(service.list());
    }

    @GetMapping("/get/{id}")
    public Result<T> get(@PathVariable Long id) {
        return Result.build(service.getById(id));
    }

    @PostMapping("/save")
    public Result<T> save(@RequestBody T entity) {
        service.save(entity);
        return Result.build(null);
    }

    @PutMapping("/update")
    public Result<T> update(@RequestBody T entity) {
        service.updateById(entity);
        return Result.build(null);
    }

    @DeleteMapping("/delete/{id}")
    public Result<T> delete(@PathVariable Long id) {
        service.removeById(id);
        return Result.build(null);
    }
}
