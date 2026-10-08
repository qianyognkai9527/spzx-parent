package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.promo.PromoPlanService;
import com.joker.spzx.model.entity.promo.PromoPlan;
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
import java.util.Map;

/**
 * 推广计划主档维护：预算、出价、时段、人群、状态、负责人。
 * 效果数据不在这里，看 /admin/promo/report/*（那份按 campaign_id 关联本表）。
 */
@RestController
@Tag(name = "推广计划主档", description = "推广计划元数据的增删改查")
@RequestMapping("/admin/promo/plan")
public class PromoPlanController {

    @Autowired
    private PromoPlanService promoPlanService;

    @Operation(summary = "计划列表（含未确认状态的，供维护页使用）")
    @GetMapping("/list")
    public Result<List<PromoPlan>> list(@RequestParam(required = false) Integer platform,
                                        @RequestParam(required = false) Long shopId,
                                        @RequestParam(required = false) String planType,
                                        @RequestParam(required = false) Integer onlineStatus,
                                        @RequestParam(required = false) String keyword) {
        return Result.build(promoPlanService.listForManage(platform, shopId, planType, onlineStatus, keyword));
    }

    @Operation(summary = "引用计数（删除前确认用）")
    @GetMapping("/usage/{id}")
    public Result<Map<String, Long>> usage(@PathVariable Long id) {
        return Result.build(promoPlanService.usage(promoPlanService.getById(id)));
    }

    @PostMapping
    public Result<Void> create(@RequestBody PromoPlan plan) {
        String err = promoPlanService.validate(plan);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = promoPlanService.campaignConflict(plan, null);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        plan.setId(null);
        promoPlanService.savePlan(plan);
        return Result.build(null);
    }

    /** 整行覆盖：留空即清空，所以前端编辑框必须先带出原值再改 */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody PromoPlan plan) {
        PromoPlan row = promoPlanService.getById(id);
        if (row == null) {
            return Result.build(null, 204, "计划不存在");
        }
        plan.setId(id);
        String err = promoPlanService.validate(plan);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        err = promoPlanService.campaignConflict(plan, id);
        if (err != null) {
            return Result.build(null, 204, err);
        }
        promoPlanService.updatePlan(plan);
        return Result.build(null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        PromoPlan row = promoPlanService.getById(id);
        if (row == null) {
            return Result.build(null, 204, "计划不存在");
        }
        long used = promoPlanService.totalUsage(row);
        if (used > 0) {
            return Result.build(null, 204, "计划「" + row.getCampaignName() + "」已有 " + used
                    + " 条采集到的花费数据，删了主档这些数据就没有归属；可把投放状态改成停投");
        }
        promoPlanService.removePlan(id);
        return Result.build(null);
    }
}
