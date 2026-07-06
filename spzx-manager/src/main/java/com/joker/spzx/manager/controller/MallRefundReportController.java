package com.joker.spzx.manager.controller;

import com.alibaba.fastjson.JSONObject;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.manager.service.MallRefundOrderService;
import com.joker.spzx.manager.service.MallRefundRecordService;
import com.joker.spzx.model.dto.mall.OrderDetailQueryDto;
import com.joker.spzx.model.dto.mall.RefundReportGenerateDto;
import com.joker.spzx.model.dto.mall.RefundReportPageDto;
import com.joker.spzx.model.entity.oper.MallRefundOrder;
import com.joker.spzx.model.entity.oper.MallRefundRecord;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.mall.OrderReportDetailVo;
import com.joker.spzx.model.vo.mall.RefundReportVo;
import com.joker.spzx.model.vo.mall.ReportOrderVo;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
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
 * @since 2025-06-10 14:05:10
 */
@RestController
@Tag(name = "退款报表", description = "退款报表接口")
@RequestMapping("/admin/mall/refundReport")
public class MallRefundReportController {

    @Autowired
    private MallRefundRecordService mallRefundRecordService;

    @Autowired
    private MallRefundOrderService mallRefundOrderService;

    @PostMapping(value = "/submit", consumes = {MediaType.MULTIPART_FORM_DATA_VALUE})
    public Result<String> submitData(@RequestParam Map<String, Object> map, @RequestParam("excelFile") MultipartFile excelFile) {
        MallRefundRecord mallRefundRecord = JSONObject.parseObject(JSONObject.toJSONString(map), MallRefundRecord.class);
        mallRefundRecordService.submitData(mallRefundRecord, excelFile);
        return Result.build(null);
    }

    @GetMapping("/page")
    public Result<IPage<MallRefundRecord>> findByPage(RefundReportPageDto refundReportPageDto) {
        long l = System.currentTimeMillis();
        IPage<MallRefundRecord> map = mallRefundRecordService.findByPage(refundReportPageDto);
        System.out.println("耗时：" + (System.currentTimeMillis() - l));
        return Result.build(map);
    }

    @GetMapping("/detail/{id}")
    public Result<RefundReportVo> getDetail(@PathVariable Long id) {
        RefundReportVo map = mallRefundRecordService.getDetail(id);
        return Result.build(map);
    }

    @GetMapping("/orderDetail")
    public Result<IPage<MallRefundOrder>> getOrderList(OrderDetailQueryDto orderDetailQueryDto) {
        IPage<MallRefundOrder> list = mallRefundRecordService.getOrderDetail(orderDetailQueryDto);
        return Result.build(list);
    }

    @PutMapping("/updateOrder")
    public Result<String> getOrderList(@RequestBody MallRefundOrder orderDetailQueryDto) {
        mallRefundOrderService.updateById(orderDetailQueryDto);
        return Result.build(null);
    }

    @DeleteMapping("/deleteReport/{id}")
    public Result<String> removeReport(@PathVariable Long id) {
        mallRefundRecordService.deleteReport(id);
        return Result.build(null);
    }


    @PostMapping("/generateReport")
    public Result<String> generateReport(@RequestBody RefundReportGenerateDto refundReportGenerateDto) {
        mallRefundRecordService.generate(refundReportGenerateDto);
        return Result.build(null);
    }

    @Operation(summary = "获取订单报表详情（含统计卡片）")
    @GetMapping("/orderReportDetail/{id}")
    public Result<OrderReportDetailVo> getOrderReportDetail(@PathVariable Long id) {
        OrderReportDetailVo vo = mallRefundRecordService.getOrderReportDetail(id);
        return Result.build(vo);
    }

    @Operation(summary = "获取报表订单列表（含订单类型和关联货源订单）")
    @GetMapping("/reportOrders/{id}")
    public Result<List<ReportOrderVo>> getReportOrders(@PathVariable Long id,
                                                       @RequestParam(required = false) String cardType) {
        List<ReportOrderVo> list = mallRefundRecordService.getReportOrders(id, cardType);
        return Result.build(list);
    }
}
