package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.expense.ExpenseOrderService;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.expense.ExpenseOrderVo;
import com.joker.spzx.model.vo.expense.ImportResultVo;
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
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/admin/expense/order")
public class ExpenseOrderController {

    @Autowired
    private ExpenseOrderService expenseOrderService;

    @GetMapping("/list/{pageNum}/{pageSize}")
    public Result<Page<ExpenseOrderVo>> list(@PathVariable long pageNum,
                                             @PathVariable long pageSize,
                                             @RequestParam(required = false) String expenseDateBegin,
                                             @RequestParam(required = false) String expenseDateEnd,
                                             @RequestParam(required = false) String channel,
                                             @RequestParam(required = false) Long tagId,
                                             @RequestParam(required = false) String keyword) {
        LocalDate begin = parseDate(expenseDateBegin);
        LocalDate end = parseDate(expenseDateEnd);
        Page<ExpenseOrderVo> page = expenseOrderService.page(pageNum, pageSize, begin, end, channel, tagId, keyword);
        return Result.build(page);
    }

    /** 支付宝账单 CSV 导入（幂等，按交易订单号去重） */
    @PostMapping("/import")
    public Result<ImportResultVo> importCsv(@RequestParam("file") MultipartFile file) {
        if (file == null || file.isEmpty()) {
            return Result.build(null, 204, "请选择要导入的账单 CSV 文件");
        }
        String name = file.getOriginalFilename();
        if (name != null && !name.toLowerCase().endsWith(".csv")) {
            return Result.build(null, 204, "只支持 CSV 文件（支付宝账单导出）");
        }
        try {
            return Result.build(expenseOrderService.importAlipayCsv(file));
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @PostMapping
    public Result<Void> create(@RequestBody ExpenseOrderService.OrderDto dto) {
        try {
            expenseOrderService.createManual(dto);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody ExpenseOrderService.OrderDto dto) {
        try {
            expenseOrderService.update(id, dto);
            return Result.build(null);
        } catch (IllegalArgumentException e) {
            return Result.build(null, 204, e.getMessage());
        }
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        expenseOrderService.delete(id);
        return Result.build(null);
    }

    @PostMapping("/batchDelete")
    public Result<Integer> batchDelete(@RequestBody Map<String, List<Long>> body) {
        List<Long> ids = body == null ? null : body.get("ids");
        return Result.build(expenseOrderService.batchDelete(ids));
    }

    private static LocalDate parseDate(String s) {
        if (s == null || s.isBlank()) {
            return null;
        }
        return LocalDate.parse(s.trim());
    }
}
