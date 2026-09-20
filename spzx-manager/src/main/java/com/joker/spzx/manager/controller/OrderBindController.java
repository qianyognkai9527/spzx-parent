package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.OrderBindService;
import com.joker.spzx.model.entity.order.OrderBind;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
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
        return Result.build(orderBindService.findByPage(pageNum, pageSize, localOrderNo, sourceOrderNo, bindStatus));
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
