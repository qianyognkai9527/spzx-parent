package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.UserCostService;
import com.joker.spzx.model.dto.product.UserCostDto;
import com.joker.spzx.model.dto.product.UserCostPageDto;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.product.UserCostDetailVo;
import com.joker.spzx.model.vo.product.UserCostPageVo;
import com.joker.spzx.common.annotation.Log;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * <p>
 * 商品规格 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-08-25 16:12:25
 */
@RestController
@RequestMapping("/admin/user/cost")
public class UserCostController {

    @Autowired
    private UserCostService userCostService;

    @GetMapping("/findByPage")
    public Result<IPage<UserCostPageVo>> findByPage(UserCostPageDto userCostQueryDto) {
        IPage<UserCostPageVo> page = userCostService.findByPage(userCostQueryDto);
        return Result.build(page);
    }

    @GetMapping("/getDetail")
    public Result<UserCostDetailVo> getDetail(Long id) {
        UserCostDetailVo userCostDetailVo = userCostService.getDetail(id);
        return Result.build(userCostDetailVo);
    }

    @PostMapping("/save")
    @Log(title = "账单管理", businessType = 1)
    public Result<String> save(@RequestBody UserCostDto userCostDto) {
        userCostService.saveData(userCostDto);
        return Result.build(null);
    }

    @PutMapping("/update")
    @Log(title = "账单管理", businessType = 2)
    public Result<String> update(@RequestBody UserCostDto userCostDto) {
        userCostService.updateData(userCostDto);
        return Result.build(null);
    }

    @DeleteMapping("/remove")
    @Log(title = "账单管理", businessType = 3)
    public Result<String> remove(Long id) {
        userCostService.removeData(id);
        return Result.build(null);
    }

}
