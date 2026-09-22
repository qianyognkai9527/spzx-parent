package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.joker.spzx.manager.mapper.ExpenseOrderTagMapper;
import com.joker.spzx.manager.service.expense.ExpenseTagService;
import com.joker.spzx.model.entity.expense.ExpenseOrderTag;
import com.joker.spzx.model.entity.expense.ExpenseTag;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/admin/expense/tag")
public class ExpenseTagController {

    @Autowired
    private ExpenseTagService expenseTagService;

    @Autowired
    private ExpenseOrderTagMapper expenseOrderTagMapper;

    /** 全量列表（含停用；录入下拉由前端只取 status=1） */
    @GetMapping("/all")
    public Result<java.util.List<ExpenseTag>> all() {
        return Result.build(expenseTagService.listAll());
    }

    @PostMapping
    public Result<Void> create(@RequestBody ExpenseTag tag) {
        if (tag.getName() == null || tag.getName().isBlank()) {
            return Result.build(null, 204, "标签名不能为空");
        }
        String err = expenseTagService.nameConflict(tag.getName().trim(), null);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        tag.setName(tag.getName().trim());
        if (tag.getStatus() == null) {
            tag.setStatus(1);
        }
        if (tag.getSortValue() == null) {
            tag.setSortValue(0);
        }
        expenseTagService.save(tag);
        return Result.build(null);
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody ExpenseTag tag) {
        ExpenseTag row = expenseTagService.getById(id);
        if (row == null) {
            return Result.build(null, 204, "标签不存在");
        }
        if (tag.getName() != null && !tag.getName().isBlank()) {
            String err = expenseTagService.nameConflict(tag.getName().trim(), id);
            if (err != null) {
                return Result.build(null, 204, err);
            }
            row.setName(tag.getName().trim());
        }
        if (tag.getColor() != null) {
            row.setColor(tag.getColor());
        }
        if (tag.getSortValue() != null) {
            row.setSortValue(tag.getSortValue());
        }
        if (tag.getStatus() != null) {
            row.setStatus(tag.getStatus());
        }
        expenseTagService.updateById(row);
        return Result.build(null);
    }

    /** 被订单引用的标签拒绝删除（历史关联保留） */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        if (!expenseTagService.removeById(id)) {
            return Result.build(null, 204, "标签不存在");
        }
        return Result.build(null);
    }

    /** 引用计数（前端删除前确认用） */
    @GetMapping("/usage/{id}")
    public Result<Long> usage(@PathVariable Long id) {
        return Result.build(expenseOrderTagMapper.selectCount(new LambdaQueryWrapper<ExpenseOrderTag>()
                .eq(ExpenseOrderTag::getTagId, id)));
    }
}
