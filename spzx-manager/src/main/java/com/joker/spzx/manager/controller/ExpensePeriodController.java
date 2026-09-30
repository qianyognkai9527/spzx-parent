package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.expense.ExpensePeriodService;
import com.joker.spzx.model.entity.expense.ExpensePeriodClose;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.format.DateTimeParseException;
import java.util.List;

/**
 * 对账关账月份管理：关账后该月账单禁改/禁删，重复导入自动跳过。
 */
@RestController
@RequestMapping("/admin/expense/period")
public class ExpensePeriodController {

    @Autowired
    private ExpensePeriodService periodService;

    public record CloseDto(String period, String remark) {
    }

    @GetMapping("/list")
    public Result<List<ExpensePeriodClose>> list() {
        return Result.build(periodService.list());
    }

    @PostMapping("/close")
    public Result<Void> close(@RequestBody CloseDto dto) {
        if (dto == null || dto.period() == null || dto.period().isBlank()) {
            return Result.build(null, 204, "请选择要关账的月份");
        }
        try {
            periodService.close(dto.period().trim(), dto.remark());
            return Result.build(null);
        } catch (DateTimeParseException e) {
            return Result.build(null, 204, "月份格式应为 yyyy-MM，如 2026-08");
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @DeleteMapping("/{period}")
    public Result<Void> reopen(@PathVariable String period) {
        try {
            periodService.reopen(period);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }
}
