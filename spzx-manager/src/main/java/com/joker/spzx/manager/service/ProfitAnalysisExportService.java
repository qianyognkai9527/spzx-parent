package com.joker.spzx.manager.service;

import com.alibaba.excel.EasyExcel;
import com.alibaba.excel.annotation.ExcelProperty;
import com.joker.spzx.model.entity.oper.ProfitAnalysisRecord;
import jakarta.servlet.http.HttpServletResponse;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * 利润分析记录导出 xlsx（按商品全部记录，一次下全，便于贴给老板/存档）。
 */
@Service
public class ProfitAnalysisExportService {

    @Autowired
    private ProfitAnalysisRecordService recordService;

    // EasyExcel 的 BeanMap 读不了 record 组件值（与 KwExportService 同因），必须 POJO
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Row {
        @ExcelProperty("商品ID")
        private Long productId;
        @ExcelProperty("商品标题")
        private String productTitle;
        @ExcelProperty("平台")
        private String platform;
        @ExcelProperty("售价")
        private BigDecimal price;
        @ExcelProperty("货源价")
        private BigDecimal cost;
        @ExcelProperty("发出运费")
        private BigDecimal freight;
        @ExcelProperty("退回运费")
        private BigDecimal returnFreight;
        @ExcelProperty("运费险/单")
        private BigDecimal freightInsurance;
        @ExcelProperty("选货运费")
        private BigDecimal sourcingFreight;
        @ExcelProperty("推广费/单")
        private BigDecimal adCost;
        @ExcelProperty("佣金率%")
        private BigDecimal commissionRate;
        @ExcelProperty("手续费率%")
        private BigDecimal paymentFeeRate;
        @ExcelProperty("退款率%")
        private BigDecimal refundRate;
        @ExcelProperty("订单量")
        private Integer orderCount;
        @ExcelProperty("单笔毛利")
        private BigDecimal grossProfitPerOrder;
        @ExcelProperty("单笔净利")
        private BigDecimal perOrderNetAvg;
        @ExcelProperty("净利率%")
        private BigDecimal netMargin;
        @ExcelProperty("预估总利润")
        private BigDecimal actualTotalProfit;
        @ExcelProperty("ROI")
        private BigDecimal roi;
        @ExcelProperty("ROAS")
        private BigDecimal roas;
        @ExcelProperty("盈亏平衡售价")
        private BigDecimal breakEvenPrice;
        @ExcelProperty("盈亏平衡退款率%")
        private BigDecimal breakEvenRefundRate;
        @ExcelProperty("建议投放")
        private String canPromote;
        @ExcelProperty("分析时间")
        private String createTime;
    }

    public void export(Long productId, HttpServletResponse response) throws Exception {
        List<Row> rows = new ArrayList<>();
        for (ProfitAnalysisRecord r : recordService.listByProduct(productId)) {
            rows.add(new Row(r.getProductId(), r.getProductTitle(),
                    platformName(r.getPlatformType()),
                    r.getPrice(), r.getCost(), r.getFreight(), r.getReturnFreight(),
                    r.getFreightInsurance(), r.getSourcingFreight(), r.getAdCost(),
                    r.getCommissionRate(), r.getPaymentFeeRate(), r.getRefundRate(),
                    r.getOrderCount(), r.getGrossProfitPerOrder(), r.getPerOrderNetAvg(),
                    r.getNetMargin(), r.getActualTotalProfit(), r.getRoi(), r.getRoas(),
                    r.getBreakEvenPrice(), r.getBreakEvenRefundRate(),
                    r.getCanPromote() == null ? "" : (r.getCanPromote() == 1 ? "是" : "否"),
                    r.getCreateTime() == null ? "" : r.getCreateTime().toString()));
        }
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("profit_product_" + productId, StandardCharsets.UTF_8);
        response.setHeader("Content-Disposition", "attachment;filename=" + fileName + ".xlsx");
        EasyExcel.write(response.getOutputStream(), Row.class).sheet("利润分析").doWrite(rows);
    }

    private static String platformName(Integer t) {
        if (t == null) return "";
        return switch (t) {
            case 1 -> "淘宝";
            case 2 -> "抖音";
            default -> String.valueOf(t);
        };
    }
}
