package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.expense.ExpenseGroupService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.expense.ExpenseGroupVo;
import com.joker.spzx.model.vo.expense.ExpenseOrderVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/expense/group")
public class ExpenseGroupController {

    @Autowired
    private ExpenseGroupService expenseGroupService;

    @GetMapping("/all")
    public Result<List<ExpenseGroupVo>> all() {
        return Result.build(expenseGroupService.listWithStats());
    }

    @PostMapping
    public Result<Long> create(@RequestBody ExpenseGroupService.GroupDto dto) {
        if (dto == null || dto.groupName == null || dto.groupName.isBlank()) {
            return Result.build(null, 204, "分组名不能为空");
        }
        if (dto.groupName.trim().length() > 50) {
            return Result.build(null, 204, "分组名不能超过 50 字");
        }
        try {
            return Result.build(expenseGroupService.create(dto.groupName, dto.remark, dto.orderIds));
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody ExpenseGroupService.GroupDto dto) {
        if (dto == null) {
            return Result.build(null, 204, "参数不能为空");
        }
        if (dto.groupName != null && dto.groupName.trim().length() > 50) {
            return Result.build(null, 204, "分组名不能超过 50 字");
        }
        try {
            expenseGroupService.rename(id, dto.groupName, dto.remark);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        try {
            expenseGroupService.deleteGroup(id);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @PostMapping("/{id}/orders")
    public Result<Integer> addOrders(@PathVariable Long id, @RequestBody Map<String, List<Long>> body) {
        List<Long> ids = body == null ? null : body.get("orderIds");
        return Result.build(expenseGroupService.addOrders(id, ids));
    }

    @DeleteMapping("/{id}/orders/{orderId}")
    public Result<Void> removeOrder(@PathVariable Long id, @PathVariable Long orderId) {
        expenseGroupService.removeOrder(id, orderId);
        return Result.build(null);
    }

    @GetMapping("/{id}/orders/{pageNum}/{pageSize}")
    public Result<Page<ExpenseOrderVo>> orders(@PathVariable Long id,
                                               @PathVariable long pageNum,
                                               @PathVariable long pageSize) {
        return Result.build(expenseGroupService.pageOrders(pageNum, pageSize, id));
    }
}
