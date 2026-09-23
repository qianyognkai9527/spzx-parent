package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.expense.ExpenseStatsService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.expense.DailyAmountVo;
import com.joker.spzx.model.vo.expense.SummaryVo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/expense/stats")
public class ExpenseStatsController {

    @Autowired
    private ExpenseStatsService expenseStatsService;

    @GetMapping("/summary")
    public Result<SummaryVo> summary(@RequestParam(defaultValue = "30") int days) {
        return Result.build(expenseStatsService.summary(safeDays(days)));
    }

    @GetMapping("/daily")
    public Result<List<DailyAmountVo>> daily(@RequestParam(defaultValue = "30") int days) {
        return Result.build(expenseStatsService.daily(safeDays(days)));
    }

    @GetMapping("/byTag")
    public Result<List<Map<String, Object>>> byTag(@RequestParam(defaultValue = "30") int days) {
        return Result.build(expenseStatsService.byTag(safeDays(days)));
    }

    @GetMapping("/byChannel")
    public Result<List<Map<String, Object>>> byChannel(@RequestParam(defaultValue = "30") int days) {
        return Result.build(expenseStatsService.byChannel(safeDays(days)));
    }

    @GetMapping("/monthly")
    public Result<List<Map<String, Object>>> monthly(@RequestParam(required = false) Integer year) {
        return Result.build(expenseStatsService.monthly(year));
    }

    /** days<=0 会得到"未来日期"的空数据，统一钳制 */
    private static int safeDays(int days) {
        return Math.min(Math.max(days, 1), 3660);
    }
}
