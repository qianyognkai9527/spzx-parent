package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.mall.OrderDetailQueryDto;
import com.joker.spzx.model.dto.mall.RefundReportGenerateDto;
import com.joker.spzx.model.dto.mall.RefundReportPageDto;
import com.joker.spzx.model.entity.oper.MallRefundOrder;
import com.joker.spzx.model.entity.oper.MallRefundRecord;
import com.joker.spzx.model.vo.mall.OrderReportDetailVo;
import com.joker.spzx.model.vo.mall.RefundReportVo;
import com.joker.spzx.model.vo.mall.ReportOrderVo;
import org.springframework.web.multipart.MultipartFile;

/**
 * <p>
 * 退款分析报表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-07-10 13:49:10
 */
public interface MallRefundRecordService extends IService<MallRefundRecord> {

    void submitData(MallRefundRecord mallRefundRecord, MultipartFile excelFile);

    IPage<MallRefundRecord> findByPage(RefundReportPageDto refundReportPageDto);

    RefundReportVo getDetail(Long id);

    IPage<MallRefundOrder> getOrderDetail(OrderDetailQueryDto orderDetailQueryDto);

    void generate(RefundReportGenerateDto refundReportGenerateDto);


    void deleteReport(Long id);

    OrderReportDetailVo getOrderReportDetail(Long id);

    java.util.List<ReportOrderVo> getReportOrders(Long id, String cardType);
}
