package com.joker.spzx.manager.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallFarmOrderService;
import com.joker.spzx.model.dto.mall.FarmOrderPageDto;
import com.joker.spzx.model.entity.oper.MallFarmOrder;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.OderAllocationVo;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

/**
 * <p>
 * 补单表 前端控制器
 * </p>
 *
 * @author joker
 * @since 2025-05-06 17:21:06
 */
@RestController
@RequestMapping("/admin/mall/farmOrder")
public class MallFarmOrderController {

    @Autowired
    private MallFarmOrderService mallFarmOrderService;

    @GetMapping("/findByPage")
    public Result<IPage<MallFarmOrder>> findByPage(FarmOrderPageDto farmOrderPageDto) {

        IPage<MallFarmOrder> page = mallFarmOrderService.findByPage(farmOrderPageDto);
        return Result.build(page);
    }

    @PostMapping("/save")
    public Result<MallFarmOrder> saveData(@RequestBody MallFarmOrder farmOrderPageDto) {
        mallFarmOrderService.saveData(farmOrderPageDto);
        return Result.build(null);
    }

    @PutMapping("/update")
    public Result<MallFarmOrder> updateData(@RequestBody MallFarmOrder farmOrderPageDto) {
        mallFarmOrderService.updateData(farmOrderPageDto);
        return Result.build(null);
    }

    @PostMapping("/allocate")
    public Result<MallFarmOrder> allocateData(@RequestBody OderAllocationVo oderAllocationVo) {
        mallFarmOrderService.allocateResources(oderAllocationVo);
        return Result.build(null);
    }

    @PostMapping("/gennerShouBuy")
    public void gennerShouBuy(@RequestBody List<Long> orderIdList, HttpServletResponse response) {
        mallFarmOrderService.gennerShowBuy(orderIdList, response);
    }

    @PostMapping(value = "/importOrder", consumes = {MediaType.MULTIPART_FORM_DATA_VALUE})
    public Result<String> importOrderData(@RequestPart("file") MultipartFile file, @RequestParam Map<String, Object> bodyMap) {
        mallFarmOrderService.importOrderData(file, bodyMap);
        return Result.build(null);
    }

}

