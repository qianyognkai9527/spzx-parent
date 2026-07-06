package com.joker.spzx.manager.controller;

import com.joker.spzx.manager.service.MallOrderResourceService;
import com.joker.spzx.model.entity.oper.MallOrderResource;
import com.joker.spzx.model.vo.common.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * <p>
 * 订单与图片视频关联关系表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-05-11 13:02:11
 */
@RestController
@RequestMapping("/admin/mall/orderResource")
public class MallOrderResourceController {

    @Autowired
    private MallOrderResourceService mallOrderResourceService;

    @GetMapping("/getSelectedResource")
    public Result<List<Long>> getSelectedResourceList(@RequestParam Long orderId) {
        List<Long> resourceIdList = mallOrderResourceService.getSelectResources(orderId);
        return Result.build(resourceIdList);
    }

    @GetMapping("/handInsert")
    public Result<String> handInsert() {
        mallOrderResourceService.handInsert();
        return Result.build(null);
    }

    @GetMapping("/updateDataTest")
    public Result<String> handInsert2() {
        mallOrderResourceService.handInsert2();
        return Result.build(null);
    }
}
