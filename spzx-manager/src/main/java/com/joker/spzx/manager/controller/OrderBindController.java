package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.joker.spzx.manager.service.OrderBindService;
import com.joker.spzx.model.entity.order.OrderBind;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/admin/order/orderBind")
public class OrderBindController {

    @Autowired
    private OrderBindService orderBindService;

    @GetMapping("/findByPage")
    public Result<IPage<OrderBind>> findByPage(@RequestParam(defaultValue = "1") Integer pageNum,
                                               @RequestParam(defaultValue = "10") Integer pageSize,
                                               @RequestParam(required = false) String localOrderNo,
                                               @RequestParam(required = false) String sourceOrderNo,
                                               @RequestParam(required = false) Integer bindStatus) {
        Page<OrderBind> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<OrderBind> wrapper = new LambdaQueryWrapper<OrderBind>()
                .like(StringUtils.hasText(localOrderNo), OrderBind::getLocalOrderNo, localOrderNo)
                .like(StringUtils.hasText(sourceOrderNo), OrderBind::getSourceOrderNo, sourceOrderNo)
                .eq(bindStatus != null, OrderBind::getBindStatus, bindStatus)
                .eq(OrderBind::getIsDeleted, 0)
                .orderByDesc(OrderBind::getCreateTime);
        return Result.build(orderBindService.page(page, wrapper));
    }

    @GetMapping("/getById/{id}")
    public Result<OrderBind> getById(@PathVariable Long id) {
        return Result.build(orderBindService.getById(id));
    }

    @PostMapping("/save")
    public Result<String> save(@RequestBody OrderBind orderBind) {
        orderBind.setIsDeleted(0);
        orderBindService.save(orderBind);
        return Result.build(null);
    }

    @PutMapping("/update")
    public Result<String> update(@RequestBody OrderBind orderBind) {
        orderBindService.updateById(orderBind);
        return Result.build(null);
    }

    @DeleteMapping("/remove/{id}")
    public Result<String> remove(@PathVariable Long id) {
        orderBindService.removeById(id);
        return Result.build(null);
    }
}
