package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.expense.ExpenseTagRuleService;
import com.joker.spzx.model.entity.expense.ExpenseTagRule;
import com.joker.spzx.model.vo.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 账单自动打标规则：规则维护 + 先预览后落库的跑批入口。
 */
@RestController
@Tag(name = "自动打标规则", description = "账单标签规则与批量打标")
@RequestMapping("/admin/expense/rule")
public class ExpenseRuleController {

    @Autowired
    private ExpenseTagRuleService ruleService;

    @Operation(summary = "规则列表（带标签名）")
    @GetMapping("/all")
    public Result<List<ExpenseTagRule>> all() {
        return Result.build(ruleService.listAll());
    }

    @PostMapping
    public Result<Void> create(@RequestBody ExpenseTagRule rule) {
        String err = ruleService.validate(rule);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = ruleService.conflict(rule);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        ruleService.save(rule);
        return Result.build(null);
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody ExpenseTagRule rule) {
        if (ruleService.getById(id) == null) {
            return Result.build(null, 204, "规则不存在");
        }
        rule.setId(id);
        String err = ruleService.validate(rule);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = ruleService.conflict(rule);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        ruleService.update(rule);
        return Result.build(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        ruleService.delete(id);
        return Result.build(null);
    }

    /**
     * 跑一轮规则。dryRun 默认 true：先看命中数，确认了再带 dryRun=false 真写。
     * 写进去的关联不会因为重复执行而翻倍（主键 INSERT IGNORE）。
     */
    @Operation(summary = "按规则批量打标，dryRun=true 只返回预览")
    @PostMapping("/autoTag")
    public Result<ExpenseTagRuleService.AutoTagResult> autoTag(
            @RequestParam(defaultValue = "true") boolean dryRun,
            @RequestParam(defaultValue = "true") boolean onlyUntagged) {
        return Result.build(ruleService.run(dryRun, onlyUntagged));
    }
}
