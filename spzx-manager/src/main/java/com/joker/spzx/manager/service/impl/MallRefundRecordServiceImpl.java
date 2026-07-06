package com.joker.spzx.manager.service.impl;

import cn.hutool.core.lang.Snowflake;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.google.common.collect.Lists;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.excel.OrderSimpleExcelBo;
import com.joker.spzx.manager.mapper.MallAddOrderMapper;
import com.joker.spzx.manager.mapper.MallRefundOrderMapper;
import com.joker.spzx.manager.mapper.MallRefundRecordDetailMapper;
import com.joker.spzx.manager.mapper.MallRefundRecordMapper;
import com.joker.spzx.manager.mapper.OrderSourceRelationMapper;
import com.joker.spzx.manager.service.MallRefundRecordService;
import com.joker.spzx.model.dto.mall.OrderDetailQueryDto;
import com.joker.spzx.model.dto.mall.RefundReportGenerateDto;
import com.joker.spzx.model.dto.mall.RefundReportPageDto;
import com.joker.spzx.model.entity.oper.MallAddOrder;
import com.joker.spzx.model.entity.oper.MallRefundOrder;
import com.joker.spzx.model.entity.oper.MallRefundRecord;
import com.joker.spzx.model.entity.oper.MallRefundRecordDetail;
import com.joker.spzx.model.entity.order.OrderSourceRelation;
import com.joker.spzx.model.vo.mall.OrderReportDetailVo;
import com.joker.spzx.model.vo.mall.RefundReportVo;
import com.joker.spzx.model.vo.mall.ReportOrderVo;
import com.joker.spzx.model.vo.mall.ReportStatCardVo;
import com.joker.spzx.utils.AuthContextUtil;
import com.joker.spzx.utils.excel.DefaultExcelListener;
import com.joker.spzx.utils.excel.ExcelResult;
import com.joker.spzx.utils.excel.ExcelUtil;
import lombok.SneakyThrows;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Collectors;

/**
 * <p>
 * 退款分析报表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-07-10 13:49:10
 */
@Service
public class MallRefundRecordServiceImpl extends ServiceImpl<MallRefundRecordMapper, MallRefundRecord> implements MallRefundRecordService {


    @Autowired
    private MallRefundOrderMapper mallRefundOrderMapper;

    @Autowired
    private MallAddOrderMapper mallAddOrderMapper;

    @Autowired
    private MallRefundRecordDetailMapper mallRefundRecordDetailMapper;

    @Autowired
    private OrderSourceRelationMapper orderSourceRelationMapper;

    @SneakyThrows
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void submitData(MallRefundRecord mallRefundRecord, MultipartFile excelFile) {
        ExcelResult<OrderSimpleExcelBo> orderSimpleExcelBoExcelResult = ExcelUtil.importExcel(excelFile.getInputStream(), OrderSimpleExcelBo.class, new DefaultExcelListener<>(true));
        if (!orderSimpleExcelBoExcelResult.isSuccess()) {
            throw new ServiceException(500, "读取excel数据异常");
        }
        List<OrderSimpleExcelBo> list = orderSimpleExcelBoExcelResult.getList();

        Snowflake snowflake = new Snowflake(1L, 1L);
        String orderCode = snowflake.nextIdStr();
        List<MallRefundOrder> collect = list.stream().map(bo -> {
            MallRefundOrder mallRefundOrder = new MallRefundOrder();
            mallRefundOrder.setOrderId(bo.getOrderId());
            mallRefundOrder.setPayMoney(new BigDecimal(bo.getPayMoney()));
            mallRefundOrder.setRefundMoney(new BigDecimal(bo.getRefundMoney()));
            mallRefundOrder.setOrderStatus(bo.getOrderStatus());
            mallRefundOrder.setCode(orderCode);

            return mallRefundOrder;
        }).collect(Collectors.toList());
        mallRefundOrderMapper.insert(collect);
        LocalDateTime startTime = mallRefundRecord.getStartTime();
        LocalDateTime newStartTime = startTime.with(LocalTime.MIDNIGHT);
        mallRefundRecord.setStartTime(newStartTime);
        LocalDateTime newEndTime = mallRefundRecord.getEndTime().with(LocalTime.of(23, 59, 59));
        mallRefundRecord.setEndTime(newEndTime);
        mallRefundRecord.setCode(snowflake.nextIdStr());
        mallRefundRecord.setOrderDataCode(orderCode);
        mallRefundRecord.setState(1);
        mallRefundRecord.setCreateTime(LocalDateTime.now());
        mallRefundRecord.setCreateBy(AuthContextUtil.getUser().getId());
        mallRefundRecord.insert();

    }

    @Override
    public IPage<MallRefundRecord> findByPage(RefundReportPageDto refundReportPageDto) {
        IPage<MallRefundRecord> page = refundReportPageDto.getPage();
        LambdaQueryWrapper<MallRefundRecord> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(MallRefundRecord::getDelFlag, 0);
        String startDate = refundReportPageDto.getStartDate();
        if (StringUtils.isNotBlank(startDate)) {
            String dateTimeStr = startDate + " 00:00:00";
            DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
            LocalDateTime dateTime = LocalDateTime.parse(dateTimeStr, formatter);
            lambdaQueryWrapper.ge(MallRefundRecord::getCreateTime, dateTime);
        }
        if (StringUtils.isNotBlank(refundReportPageDto.getEndDate())) {
            String dateTimeStr = refundReportPageDto.getEndDate() + " 23:59:59";
            DateTimeFormatter dateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
            LocalDateTime dateTime = LocalDateTime.parse(dateTimeStr, dateTimeFormatter);
            lambdaQueryWrapper.le(MallRefundRecord::getCreateTime, dateTime);
        }
        lambdaQueryWrapper.eq(StringUtils.isNotBlank(refundReportPageDto.getCode()), MallRefundRecord::getCode, refundReportPageDto.getCode());
        this.baseMapper.selectPage(page, lambdaQueryWrapper);

        return page;
    }

    @Override
    public RefundReportVo getDetail(Long id) {
        LambdaQueryWrapper<MallRefundRecordDetail> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(MallRefundRecordDetail::getRecordId, id)
                .last(" limit 1");
        MallRefundRecordDetail mallRefundRecordDetail = mallRefundRecordDetailMapper.selectOne(lambdaQueryWrapper);
        RefundReportVo refundReportVo = new RefundReportVo();
        BeanUtils.copyProperties(mallRefundRecordDetail, refundReportVo);
        MallRefundRecord mallRefundRecord = this.getById(id);
        BeanUtils.copyProperties(mallRefundRecord, refundReportVo);
        return refundReportVo;
    }

    @Override
    public IPage<MallRefundOrder> getOrderDetail(OrderDetailQueryDto orderDetailQueryDto) {
        LambdaQueryWrapper<MallRefundOrder> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(StringUtils.isNotBlank(orderDetailQueryDto.getOrderDataCode()), MallRefundOrder::getCode, orderDetailQueryDto.getOrderDataCode());
        lambdaQueryWrapper.eq(StringUtils.isNotBlank(orderDetailQueryDto.getOrderId()), MallRefundOrder::getOrderId, orderDetailQueryDto.getOrderId());
        IPage<MallRefundOrder> page = orderDetailQueryDto.getPage();
        this.mallRefundOrderMapper.selectPage(page, lambdaQueryWrapper);
        return page;
    }

    @Override
    public void generate(RefundReportGenerateDto refundReportGenerateDto) {
        Long reportRecordId = refundReportGenerateDto.getId();
        MallRefundRecord mallRefundRecord = new MallRefundRecord();
        mallRefundRecord.setId(reportRecordId);
        mallRefundRecord.setState(2);
        mallRefundRecord.updateById();

        //开始计算订单
        mallRefundRecord = this.getById(reportRecordId);
        if (Objects.isNull(mallRefundRecord)) {
            mallRefundRecord.setRemark("报表不存在！");
            mallRefundRecord.setState(4);
            mallRefundRecord.updateById();
            throw new ServiceException(500, "订单报表不存在");
        }
        LambdaQueryWrapper<MallRefundRecordDetail> recordDetailLambdaQueryWrapper = new LambdaQueryWrapper<>();
        recordDetailLambdaQueryWrapper.eq(MallRefundRecordDetail::getRecordId, reportRecordId);
        recordDetailLambdaQueryWrapper.last(" limit 1");
        MallRefundRecordDetail mallRefundRecordDetail = this.mallRefundRecordDetailMapper.selectOne(recordDetailLambdaQueryWrapper);
        if (Objects.isNull(mallRefundRecordDetail)) {
            mallRefundRecordDetail = new MallRefundRecordDetail();
        }

        String orderDataCode = mallRefundRecord.getOrderDataCode();
        LambdaQueryWrapper<MallRefundOrder> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(MallRefundOrder::getCode, orderDataCode);
        List<MallRefundOrder> list = this.mallRefundOrderMapper.selectList(lambdaQueryWrapper);
        Map<String, MallRefundOrder> collect = list.stream().collect(Collectors.toMap(MallRefundOrder::getOrderId, v -> v));

        AtomicReference<BigDecimal> totalMoney = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> allOrderList = new AtomicReference<>(Lists.newArrayList());
        list.stream().forEach(mallRefundOrder -> {
            String orderStatus = mallRefundOrder.getOrderStatus();
            BigDecimal orderPayMoneyStr = BigDecimal.ZERO;
            switch (orderStatus) {
                case "交易成功":
                    orderPayMoneyStr = mallRefundOrder.getPayMoney();
                    break;
                case "交易关闭":
                    orderPayMoneyStr = mallRefundOrder.getRefundMoney();
                    break;
                case "卖家已发货，等待买家确认":
                    orderPayMoneyStr = mallRefundOrder.getPayMoney();
                    break;
                default:
                    orderPayMoneyStr = BigDecimal.ZERO;
                    break;
            }
            System.out.println(mallRefundOrder.getOrderId() + "  " + orderPayMoneyStr.toString());
            totalMoney.set(totalMoney.get().add(orderPayMoneyStr));
            allOrderList.get().add(mallRefundOrder.getOrderId());
        });
        mallRefundRecordDetail.setTotalPayAmount(totalMoney.get());
        mallRefundRecordDetail.setTotalCount(list.size());

        List<String> totalOrderList = allOrderList.get();
        System.out.println("总订单数：" + totalOrderList.size());
        LocalDateTime createTime = mallRefundRecord.getStartTime();
        LocalDateTime endTime = mallRefundRecord.getEndTime();

        LambdaQueryWrapper<MallAddOrder> mallAddOrderQueryWrapper = new LambdaQueryWrapper<>();
        mallAddOrderQueryWrapper.ge(MallAddOrder::getOrderTime, createTime)
                .le(MallAddOrder::getOrderTime, endTime);
        List<MallAddOrder> mallAddOrderList = mallAddOrderMapper.selectList(mallAddOrderQueryWrapper);
        Integer brushCount = mallAddOrderList.size();
        mallRefundRecordDetail.setBrushCount(brushCount);

        AtomicReference<BigDecimal> brushTotalMoneyRef = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> brushOrderListRef = new AtomicReference<>(Lists.newArrayList());
        mallAddOrderList.stream().forEach(mallAddOrder -> {
            brushTotalMoneyRef.set(brushTotalMoneyRef.get().add(new BigDecimal(mallAddOrder.getSeedMoney().toString())));
            brushOrderListRef.get().add(mallAddOrder.getTbOrderId());
        });
        System.out.println("刷单订单数：" + brushOrderListRef.get().size());
        mallRefundRecordDetail.setBrushMoney(brushTotalMoneyRef.get());
        BigDecimal multiply = new BigDecimal(brushCount.toString()).multiply(new BigDecimal("7.3"));
        mallRefundRecordDetail.setBrushOtherMoney(multiply);
        totalOrderList.removeAll(brushOrderListRef.get());
        System.out.println("排除刷单订单后有效订单数：" + totalOrderList.size());
        //有效订单
        List<MallRefundOrder> effectOrderList = totalOrderList.stream().map(orderId -> {
            MallRefundOrder mallRefundOrder = collect.get(orderId);
            return mallRefundOrder;
        }).collect(Collectors.toList());
        //过滤出退款订单
        AtomicReference<BigDecimal> totalRefundMoneyRef = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> refundOrderListRef = new AtomicReference<>(Lists.newArrayList());

        AtomicReference<BigDecimal> pendingRefundMoneyRef = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> pendingOrderListRef = new AtomicReference<>(Lists.newArrayList());

        AtomicReference<BigDecimal> successRefundMoneyRef = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> successOrderListRef = new AtomicReference<>(Lists.newArrayList());
        effectOrderList.stream().forEach(mallRefundOrder -> {
            BigDecimal refundMoney = mallRefundOrder.getRefundMoney();
            String orderId = mallRefundOrder.getOrderId();
            String orderStatus = mallRefundOrder.getOrderStatus();
            if (refundMoney.compareTo(BigDecimal.ZERO) > 0) {
                //有退款金额
                totalRefundMoneyRef.set(totalRefundMoneyRef.get().add(refundMoney));
                refundOrderListRef.get().add(orderId);
            } else if (refundMoney.compareTo(BigDecimal.ZERO) == 0 && orderStatus.equals("交易成功")) {
                //无退款金额
                successOrderListRef.get().add(orderId);
                successRefundMoneyRef.set(successRefundMoneyRef.get().add(refundMoney));
            }
            if (refundMoney.compareTo(BigDecimal.ZERO) == 0 && orderStatus.equals("卖家已发货，等待买家确认")) {
                pendingOrderListRef.get().add(orderId);
                pendingRefundMoneyRef.set(pendingRefundMoneyRef.get().add(refundMoney));
            }

        });
        List<String> refundOrderList = refundOrderListRef.get();
        mallRefundRecordDetail.setRefundCount(refundOrderList.size());
        System.out.println("退款订单数：" + refundOrderList.size());
        System.out.println("退款订单金额：" + totalRefundMoneyRef.get());
        System.out.println("交易成功订单数：" + successOrderListRef.get().size());
        System.out.println("待定订单数：" + pendingOrderListRef.get().size());

        mallRefundRecordDetail.setRefundMoney(totalRefundMoneyRef.get());
        mallRefundRecordDetail.setPendingCount(pendingOrderListRef.get().size());

        mallRefundRecordDetail.setSuccessCount(successOrderListRef.get().size());
        mallRefundRecordDetail.setSuccessMoney(successRefundMoneyRef.get());

        mallRefundRecordDetail.setPendingCount(pendingOrderListRef.get().size());
        mallRefundRecordDetail.setPendingMoney(pendingRefundMoneyRef.get());
        //成交金额
        double successMoney = totalOrderList.stream().map(orderId -> {
            MallRefundOrder mallRefundOrder = collect.get(orderId);
            return mallRefundOrder;
        }).collect(Collectors.toList()).stream().mapToDouble(mallRefundOrder -> {
            return mallRefundOrder.getPayMoney().doubleValue();
        }).sum();

        //当前退款率
        BigDecimal currentTotalOrder = new BigDecimal(successOrderListRef.get().size() + refundOrderList.size() + "");
        BigDecimal currentRefundRate = new BigDecimal(refundOrderList.size() + "").divide(currentTotalOrder, 4, RoundingMode.HALF_UP);
        mallRefundRecordDetail.setCurrentRefundRate(currentRefundRate);
        //乐观退款率
        BigDecimal optimistTotalOrder = currentTotalOrder.add(new BigDecimal(pendingOrderListRef.get().size() + ""));
        BigDecimal optimistRefundRate = new BigDecimal(refundOrderList.size() + "").divide(optimistTotalOrder, 4, RoundingMode.HALF_UP);
        mallRefundRecordDetail.setOptimistRefundRate(optimistRefundRate);
        //悲观退款率
        BigDecimal pessimistTotalOrder = new BigDecimal(refundOrderList.size() + "").add(new BigDecimal(pendingOrderListRef.get().size() + ""));
        BigDecimal pessimistRefundRate = pessimistTotalOrder.divide(optimistTotalOrder, 4, RoundingMode.HALF_UP);
        mallRefundRecordDetail.setPessimistRefundRate(pessimistRefundRate);
        System.out.println();
        totalOrderList.removeAll(refundOrderList);
        System.out.println("排除刷单、退款单后的成交订单数量：" + totalOrderList.size());

        BigDecimal subtract = totalMoney.get().subtract(brushTotalMoneyRef.get())
                .subtract(multiply).subtract(totalRefundMoneyRef.get())
                .subtract(mallRefundRecord.getCrowdPromotion())
                .subtract(mallRefundRecord.getSitePromotion())
                .subtract(mallRefundRecord.getKeywordPromotion())
                .subtract(mallRefundRecord.getSmartPromotion());
        mallRefundRecordDetail.setProfitAmount(subtract);
        mallRefundRecordDetail.setRecordId(mallRefundRecord.getId());
        mallRefundRecordDetail.insertOrUpdate();
        mallRefundRecord.setState(3);
        mallRefundRecord.updateById();
    }

    @Override
    public void deleteReport(Long id) {
        MallRefundRecord mallRefundRecord = new MallRefundRecord();
        mallRefundRecord.setId(id);
        mallRefundRecord.setDelFlag(1);
        this.updateById(mallRefundRecord);
    }

    @Override
    public OrderReportDetailVo getOrderReportDetail(Long id) {
        MallRefundRecord record = this.getById(id);
        if (Objects.isNull(record)) {
            throw new ServiceException(500, "报表不存在");
        }
        OrderReportDetailVo vo = new OrderReportDetailVo();
        vo.setId(record.getId());
        vo.setCode(record.getCode());
        vo.setName(record.getName());
        vo.setOrderDataCode(record.getOrderDataCode());
        vo.setState(record.getState());
        vo.setStartTime(record.getStartTime());
        vo.setEndTime(record.getEndTime());
        vo.setTotalAmount(record.getTotalAmount());
        vo.setSmartPromotion(record.getSmartPromotion());
        vo.setCrowdPromotion(record.getCrowdPromotion());
        vo.setSitePromotion(record.getSitePromotion());
        vo.setKeywordPromotion(record.getKeywordPromotion());

        // 获取详情统计
        LambdaQueryWrapper<MallRefundRecordDetail> detailWrapper = new LambdaQueryWrapper<>();
        detailWrapper.eq(MallRefundRecordDetail::getRecordId, id).last(" limit 1");
        MallRefundRecordDetail detail = mallRefundRecordDetailMapper.selectOne(detailWrapper);

        // 构建统计卡片
        List<ReportStatCardVo> cards = Lists.newArrayList();

        int totalCount = 0, brushCount = 0, successCount = 0, refundCount = 0, pendingCount = 0;
        BigDecimal totalPayAmount = BigDecimal.ZERO, profitAmount = BigDecimal.ZERO;
        BigDecimal successMoney = BigDecimal.ZERO, refundMoney = BigDecimal.ZERO, brushMoney = BigDecimal.ZERO;

        if (detail != null) {
            totalCount = detail.getTotalCount() != null ? detail.getTotalCount() : 0;
            brushCount = detail.getBrushCount() != null ? detail.getBrushCount() : 0;
            successCount = detail.getSuccessCount() != null ? detail.getSuccessCount() : 0;
            refundCount = detail.getRefundCount() != null ? detail.getRefundCount() : 0;
            pendingCount = detail.getPendingCount() != null ? detail.getPendingCount() : 0;
            totalPayAmount = detail.getTotalPayAmount() != null ? detail.getTotalPayAmount() : BigDecimal.ZERO;
            profitAmount = detail.getProfitAmount() != null ? detail.getProfitAmount() : BigDecimal.ZERO;
            successMoney = detail.getSuccessMoney() != null ? detail.getSuccessMoney() : BigDecimal.ZERO;
            refundMoney = detail.getRefundMoney() != null ? detail.getRefundMoney() : BigDecimal.ZERO;
            brushMoney = detail.getBrushMoney() != null ? detail.getBrushMoney() : BigDecimal.ZERO;
        }

        // 如果还没有生成过，实时计算
        if (detail == null && StringUtils.isNotBlank(record.getOrderDataCode())) {
            LambdaQueryWrapper<MallRefundOrder> orderWrapper = new LambdaQueryWrapper<>();
            orderWrapper.eq(MallRefundOrder::getCode, record.getOrderDataCode());
            List<MallRefundOrder> allOrders = mallRefundOrderMapper.selectList(orderWrapper);
            totalCount = allOrders.size();

            // 获取补单订单
            LambdaQueryWrapper<MallAddOrder> brushWrapper = new LambdaQueryWrapper<>();
            brushWrapper.ge(MallAddOrder::getOrderTime, record.getStartTime())
                    .le(MallAddOrder::getOrderTime, record.getEndTime());
            List<MallAddOrder> brushOrders = mallAddOrderMapper.selectList(brushWrapper);
            java.util.Set<String> brushOrderIds = brushOrders.stream()
                    .map(MallAddOrder::getTbOrderId)
                    .collect(Collectors.toSet());
            brushCount = (int) allOrders.stream().filter(o -> brushOrderIds.contains(o.getOrderId())).count();

            for (MallRefundOrder order : allOrders) {
                if (brushOrderIds.contains(order.getOrderId())) continue;
                if (order.getRefundMoney() != null && order.getRefundMoney().compareTo(BigDecimal.ZERO) > 0) {
                    refundCount++;
                    refundMoney = refundMoney.add(order.getRefundMoney());
                } else if ("交易成功".equals(order.getOrderStatus())) {
                    successCount++;
                    successMoney = successMoney.add(order.getPayMoney() != null ? order.getPayMoney() : BigDecimal.ZERO);
                } else if ("卖家已发货，等待买家确认".equals(order.getOrderStatus())) {
                    pendingCount++;
                }
            }
        }

        int unknownCount = totalCount - brushCount - successCount - refundCount - pendingCount;
        if (unknownCount < 0) unknownCount = 0;

        vo.setTotalPayAmount(totalPayAmount);
        vo.setProfitAmount(profitAmount);

        // 总订单数卡片
        ReportStatCardVo totalCard = new ReportStatCardVo();
        totalCard.setCardType("total");
        totalCard.setCardTitle("总订单数");
        totalCard.setCount(totalCount);
        totalCard.setAmount(totalPayAmount);
        totalCard.setColor("#409eff");
        totalCard.setIcon("Document");
        cards.add(totalCard);

        // 补单单量卡片
        ReportStatCardVo brushCard = new ReportStatCardVo();
        brushCard.setCardType("brush");
        brushCard.setCardTitle("补单单量");
        brushCard.setCount(brushCount);
        brushCard.setAmount(brushMoney);
        brushCard.setColor("#e6a23c");
        brushCard.setIcon("Warning");
        cards.add(brushCard);

        // 真实订单卡片
        ReportStatCardVo realCard = new ReportStatCardVo();
        realCard.setCardType("real");
        realCard.setCardTitle("真实订单");
        realCard.setCount(successCount);
        realCard.setAmount(successMoney);
        realCard.setColor("#67c23a");
        realCard.setIcon("CircleCheck");
        cards.add(realCard);

        // 退款订单卡片
        ReportStatCardVo refundCard = new ReportStatCardVo();
        refundCard.setCardType("refund");
        refundCard.setCardTitle("退款订单");
        refundCard.setCount(refundCount);
        refundCard.setAmount(refundMoney);
        refundCard.setColor("#f56c6c");
        refundCard.setIcon("CircleClose");
        cards.add(refundCard);

        // 待定订单卡片
        ReportStatCardVo pendingCard = new ReportStatCardVo();
        pendingCard.setCardType("pending");
        pendingCard.setCardTitle("待定订单");
        pendingCard.setCount(pendingCount);
        pendingCard.setColor("#909399");
        pendingCard.setIcon("Question");
        cards.add(pendingCard);

        // 未知订单卡片
        ReportStatCardVo unknownCard = new ReportStatCardVo();
        unknownCard.setCardType("unknown");
        unknownCard.setCardTitle("未知订单");
        unknownCard.setCount(unknownCount);
        unknownCard.setColor("#9c27b0");
        unknownCard.setIcon("Question");
        cards.add(unknownCard);

        vo.setStatCards(cards);
        return vo;
    }

    @Override
    public List<ReportOrderVo> getReportOrders(Long id, String cardType) {
        MallRefundRecord record = this.getById(id);
        if (Objects.isNull(record)) {
            throw new ServiceException(500, "报表不存在");
        }

        // 获取报表所有订单
        LambdaQueryWrapper<MallRefundOrder> orderWrapper = new LambdaQueryWrapper<>();
        orderWrapper.eq(MallRefundOrder::getCode, record.getOrderDataCode());
        List<MallRefundOrder> allOrders = mallRefundOrderMapper.selectList(orderWrapper);

        // 获取补单订单ID集合
        LambdaQueryWrapper<MallAddOrder> brushWrapper = new LambdaQueryWrapper<>();
        brushWrapper.ge(MallAddOrder::getOrderTime, record.getStartTime())
                .le(MallAddOrder::getOrderTime, record.getEndTime());
        List<MallAddOrder> brushOrders = mallAddOrderMapper.selectList(brushWrapper);
        java.util.Set<String> brushOrderIds = brushOrders.stream()
                .map(MallAddOrder::getTbOrderId)
                .collect(Collectors.toSet());

        // 获取所有关联的货源订单
        List<String> orderIds = allOrders.stream().map(MallRefundOrder::getOrderId).collect(Collectors.toList());
        java.util.Map<String, List<OrderSourceRelation>> sourceOrderMap = new java.util.HashMap<>();
        if (!orderIds.isEmpty()) {
            LambdaQueryWrapper<OrderSourceRelation> sourceWrapper = new LambdaQueryWrapper<>();
            sourceWrapper.in(OrderSourceRelation::getOrderNo, orderIds);
            List<OrderSourceRelation> sourceOrders = orderSourceRelationMapper.selectList(sourceWrapper);
            sourceOrderMap = sourceOrders.stream()
                    .collect(Collectors.groupingBy(OrderSourceRelation::getOrderNo));
        }

        // 构建结果
        List<ReportOrderVo> result = Lists.newArrayList();
        for (MallRefundOrder order : allOrders) {
            ReportOrderVo vo = new ReportOrderVo();
            vo.setId(order.getId());
            vo.setOrderId(order.getOrderId());
            vo.setPayMoney(order.getPayMoney());
            vo.setRefundMoney(order.getRefundMoney());
            vo.setOrderStatus(order.getOrderStatus());

            // 判断订单类型
            String orderType;
            String orderTypeDesc;
            if (brushOrderIds.contains(order.getOrderId())) {
                orderType = "brush";
                orderTypeDesc = "补单";
            } else if (order.getRefundMoney() != null && order.getRefundMoney().compareTo(BigDecimal.ZERO) > 0) {
                orderType = "refund";
                orderTypeDesc = "真实订单-退款";
            } else if ("交易成功".equals(order.getOrderStatus())) {
                orderType = "real";
                orderTypeDesc = "真实订单";
            } else if ("卖家已发货，等待买家确认".equals(order.getOrderStatus())) {
                orderType = "pending";
                orderTypeDesc = "真实订单-待定";
            } else {
                orderType = "unknown";
                orderTypeDesc = "未知";
            }
            vo.setOrderType(orderType);
            vo.setOrderTypeDesc(orderTypeDesc);

            // 关联货源订单
            vo.setSourceOrders(sourceOrderMap.getOrDefault(order.getOrderId(), Lists.newArrayList()));

            // 按卡片类型过滤
            if (StringUtils.isNotBlank(cardType)) {
                if (cardType.equals("total")) {
                    result.add(vo);
                } else if (cardType.equals(vo.getOrderType())) {
                    result.add(vo);
                }
            } else {
                result.add(vo);
            }
        }

        return result;
    }
}
