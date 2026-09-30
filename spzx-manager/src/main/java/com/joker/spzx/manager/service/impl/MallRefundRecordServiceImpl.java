package com.joker.spzx.manager.service.impl;

import cn.hutool.core.lang.Snowflake;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.google.common.collect.Lists;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.common.util.SqlConstants;
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
import lombok.extern.slf4j.Slf4j;
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
@Slf4j
@Service
public class MallRefundRecordServiceImpl extends ServiceImpl<MallRefundRecordMapper, MallRefundRecord> implements MallRefundRecordService {

    private static final String ORDER_STATUS_SUCCESS = "交易成功";
    private static final String ORDER_STATUS_CLOSED = "交易关闭";
    private static final String ORDER_STATUS_SHIPPED_WAIT = "卖家已发货，等待买家确认";

    private static final String CARD_TYPE_TOTAL = "total";
    private static final String CARD_TYPE_BRUSH = "brush";
    private static final String CARD_TYPE_REAL = "real";
    private static final String CARD_TYPE_REFUND = "refund";
    private static final String CARD_TYPE_PENDING = "pending";
    private static final String CARD_TYPE_UNKNOWN = "unknown";

    @Autowired
    private MallRefundOrderMapper mallRefundOrderMapper;

    @Autowired
    private MallAddOrderMapper mallAddOrderMapper;

    @Autowired
    private MallRefundRecordDetailMapper mallRefundRecordDetailMapper;

    @Autowired
    private com.joker.spzx.manager.service.platform.PlatformRegistryService platformRegistryService;

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

        // 报表必须带平台，否则整条链路（报表/批次明细/分析明细）的 platform_type 与 shop_id 全是 NULL，
        // 平台与店铺维度就永久缺失。历史数据由 sql/backfill_platform_type_taobao.sql 回填。
        Integer platformType = mallRefundRecord.getPlatformType();
        if (platformType == null) {
            throw new ServiceException(500, "请选择报表所属平台");
        }
        Long shopId = platformRegistryService.defaultShopId(platformType);

        Snowflake snowflake = new Snowflake(1L, 1L);
        String orderCode = snowflake.nextIdStr();
        List<MallRefundOrder> collect = list.stream().map(bo -> {
            MallRefundOrder mallRefundOrder = new MallRefundOrder();
            mallRefundOrder.setOrderId(bo.getOrderId());
            mallRefundOrder.setPayMoney(new BigDecimal(bo.getPayMoney()));
            mallRefundOrder.setRefundMoney(new BigDecimal(bo.getRefundMoney()));
            mallRefundOrder.setOrderStatus(bo.getOrderStatus());
            mallRefundOrder.setCode(orderCode);
            mallRefundOrder.setPlatformType(platformType);
            mallRefundOrder.setShopId(shopId);

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
        mallRefundRecord.setShopId(shopId);
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
        // 前端的平台 Tab 一直在传 platformType，但 DTO 里没这个字段，切 Tab 等于没筛
        lambdaQueryWrapper.eq(refundReportPageDto.getPlatformType() != null, MallRefundRecord::getPlatformType, refundReportPageDto.getPlatformType());
        lambdaQueryWrapper.eq(refundReportPageDto.getShopId() != null, MallRefundRecord::getShopId, refundReportPageDto.getShopId());
        this.baseMapper.selectPage(page, lambdaQueryWrapper);

        return page;
    }

    @Override
    public RefundReportVo getDetail(Long id) {
        LambdaQueryWrapper<MallRefundRecordDetail> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(MallRefundRecordDetail::getRecordId, id)
                .last(SqlConstants.LIMIT_1);
        MallRefundRecordDetail mallRefundRecordDetail = mallRefundRecordDetailMapper.selectOne(lambdaQueryWrapper);
        MallRefundRecord mallRefundRecord = this.getById(id);
        if (Objects.isNull(mallRefundRecordDetail) || Objects.isNull(mallRefundRecord)) {
            throw new ServiceException(500, "报表不存在或尚未生成完成");
        }
        RefundReportVo refundReportVo = new RefundReportVo();
        BeanUtils.copyProperties(mallRefundRecordDetail, refundReportVo);
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
    @Transactional(rollbackFor = Exception.class)
    public void generate(RefundReportGenerateDto refundReportGenerateDto) {
        Long reportRecordId = refundReportGenerateDto.getId();
        MallRefundRecord mallRefundRecord = new MallRefundRecord();
        mallRefundRecord.setId(reportRecordId);
        mallRefundRecord.setState(2);
        mallRefundRecord.updateById();

        //开始计算订单
        mallRefundRecord = this.getById(reportRecordId);
        if (Objects.isNull(mallRefundRecord)) {
            throw new ServiceException(500, "订单报表不存在");
        }
        LambdaQueryWrapper<MallRefundRecordDetail> recordDetailLambdaQueryWrapper = new LambdaQueryWrapper<>();
        recordDetailLambdaQueryWrapper.eq(MallRefundRecordDetail::getRecordId, reportRecordId);
        recordDetailLambdaQueryWrapper.last(SqlConstants.LIMIT_1);
        MallRefundRecordDetail mallRefundRecordDetail = this.mallRefundRecordDetailMapper.selectOne(recordDetailLambdaQueryWrapper);
        if (Objects.isNull(mallRefundRecordDetail)) {
            mallRefundRecordDetail = new MallRefundRecordDetail();
        }

        String orderDataCode = mallRefundRecord.getOrderDataCode();
        LambdaQueryWrapper<MallRefundOrder> lambdaQueryWrapper = new LambdaQueryWrapper<>();
        lambdaQueryWrapper.eq(MallRefundOrder::getCode, orderDataCode)
                .select(MallRefundOrder::getOrderId, MallRefundOrder::getOrderStatus,
                        MallRefundOrder::getPayMoney, MallRefundOrder::getRefundMoney);
        List<MallRefundOrder> list = this.mallRefundOrderMapper.selectList(lambdaQueryWrapper);
        Map<String, MallRefundOrder> collect = list.stream()
                .collect(Collectors.toMap(MallRefundOrder::getOrderId, v -> v, (a, b) -> a));

        AtomicReference<BigDecimal> totalMoney = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> allOrderList = new AtomicReference<>(Lists.newArrayList());
        list.stream().forEach(mallRefundOrder -> {
            String orderStatus = mallRefundOrder.getOrderStatus();
            BigDecimal orderPayMoneyStr = BigDecimal.ZERO;
            switch (orderStatus) {
                case ORDER_STATUS_SUCCESS:
                    orderPayMoneyStr = nvl(mallRefundOrder.getPayMoney());
                    break;
                case ORDER_STATUS_CLOSED:
                    orderPayMoneyStr = nvl(mallRefundOrder.getRefundMoney());
                    break;
                case ORDER_STATUS_SHIPPED_WAIT:
                    orderPayMoneyStr = nvl(mallRefundOrder.getPayMoney());
                    break;
                default:
                    orderPayMoneyStr = BigDecimal.ZERO;
                    break;
            }
            log.debug("订单 {} 应收金额 {}", mallRefundOrder.getOrderId(), orderPayMoneyStr);
            totalMoney.set(totalMoney.get().add(orderPayMoneyStr));
            allOrderList.get().add(mallRefundOrder.getOrderId());
        });
        mallRefundRecordDetail.setTotalPayAmount(totalMoney.get());
        mallRefundRecordDetail.setTotalCount(list.size());

        List<String> totalOrderList = allOrderList.get();
        log.debug("总订单数：{}", totalOrderList.size());
        LocalDateTime createTime = mallRefundRecord.getStartTime();
        LocalDateTime endTime = mallRefundRecord.getEndTime();

        LambdaQueryWrapper<MallAddOrder> mallAddOrderQueryWrapper = new LambdaQueryWrapper<>();
        mallAddOrderQueryWrapper.ge(MallAddOrder::getOrderTime, createTime)
                .le(MallAddOrder::getOrderTime, endTime)
                .select(MallAddOrder::getTbOrderId, MallAddOrder::getSeedMoney);
        List<MallAddOrder> mallAddOrderList = mallAddOrderMapper.selectList(mallAddOrderQueryWrapper);
        Integer brushCount = mallAddOrderList.size();
        mallRefundRecordDetail.setBrushCount(brushCount);

        AtomicReference<BigDecimal> brushTotalMoneyRef = new AtomicReference<>(BigDecimal.ZERO);
        AtomicReference<List<String>> brushOrderListRef = new AtomicReference<>(Lists.newArrayList());
        mallAddOrderList.stream().forEach(mallAddOrder -> {
            Double seed = mallAddOrder.getSeedMoney();
            brushTotalMoneyRef.set(brushTotalMoneyRef.get().add(seed == null ? BigDecimal.ZERO : BigDecimal.valueOf(seed)));
            brushOrderListRef.get().add(mallAddOrder.getTbOrderId());
        });
        log.debug("刷单订单数：{}", brushOrderListRef.get().size());
        mallRefundRecordDetail.setBrushMoney(brushTotalMoneyRef.get());
        BigDecimal multiply = new BigDecimal(brushCount.toString()).multiply(new BigDecimal("7.3"));
        mallRefundRecordDetail.setBrushOtherMoney(multiply);
        totalOrderList.removeAll(brushOrderListRef.get());
        log.debug("排除刷单订单后有效订单数：{}", totalOrderList.size());
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
            BigDecimal payMoney = mallRefundOrder.getPayMoney() != null ? mallRefundOrder.getPayMoney() : BigDecimal.ZERO;
            String orderId = mallRefundOrder.getOrderId();
            String orderStatus = mallRefundOrder.getOrderStatus();
            if (refundMoney.compareTo(BigDecimal.ZERO) > 0) {
                //有退款金额
                totalRefundMoneyRef.set(totalRefundMoneyRef.get().add(refundMoney));
                refundOrderListRef.get().add(orderId);
            } else if (refundMoney.compareTo(BigDecimal.ZERO) == 0 && orderStatus.equals(ORDER_STATUS_SUCCESS)) {
                //无退款金额
                successOrderListRef.get().add(orderId);
                successRefundMoneyRef.set(successRefundMoneyRef.get().add(payMoney));
            }
            if (refundMoney.compareTo(BigDecimal.ZERO) == 0 && orderStatus.equals(ORDER_STATUS_SHIPPED_WAIT)) {
                pendingOrderListRef.get().add(orderId);
                pendingRefundMoneyRef.set(pendingRefundMoneyRef.get().add(payMoney));
            }

        });
        List<String> refundOrderList = refundOrderListRef.get();
        mallRefundRecordDetail.setRefundCount(refundOrderList.size());
        log.debug("退款订单数：{}，退款订单金额：{}，交易成功订单数：{}，待定订单数：{}",
                refundOrderList.size(), totalRefundMoneyRef.get(), successOrderListRef.get().size(), pendingOrderListRef.get().size());

        mallRefundRecordDetail.setRefundMoney(totalRefundMoneyRef.get());
        mallRefundRecordDetail.setPendingCount(pendingOrderListRef.get().size());

        mallRefundRecordDetail.setSuccessCount(successOrderListRef.get().size());
        mallRefundRecordDetail.setSuccessMoney(successRefundMoneyRef.get());

        mallRefundRecordDetail.setPendingCount(pendingOrderListRef.get().size());
        mallRefundRecordDetail.setPendingMoney(pendingRefundMoneyRef.get());
        //当前退款率（空数据时率置 0，避免除零导致报表卡死在生成中）
        BigDecimal currentTotalOrder = new BigDecimal(successOrderListRef.get().size() + refundOrderList.size() + "");
        BigDecimal refundCount = new BigDecimal(refundOrderList.size() + "");
        mallRefundRecordDetail.setCurrentRefundRate(safeRate(refundCount, currentTotalOrder));
        //乐观退款率
        BigDecimal optimistTotalOrder = currentTotalOrder.add(new BigDecimal(pendingOrderListRef.get().size() + ""));
        mallRefundRecordDetail.setOptimistRefundRate(safeRate(refundCount, optimistTotalOrder));
        //悲观退款率
        BigDecimal pessimistTotalOrder = refundCount.add(new BigDecimal(pendingOrderListRef.get().size() + ""));
        mallRefundRecordDetail.setPessimistRefundRate(safeRate(pessimistTotalOrder, optimistTotalOrder));
        totalOrderList.removeAll(refundOrderList);
        log.debug("排除刷单、退款单后的成交订单数量：{}", totalOrderList.size());

        BigDecimal subtract = totalMoney.get().subtract(brushTotalMoneyRef.get())
                .subtract(multiply).subtract(totalRefundMoneyRef.get())
                .subtract(nvl(mallRefundRecord.getCrowdPromotion()))
                .subtract(nvl(mallRefundRecord.getSitePromotion()))
                .subtract(nvl(mallRefundRecord.getKeywordPromotion()))
                .subtract(nvl(mallRefundRecord.getSmartPromotion()));
        mallRefundRecordDetail.setProfitAmount(subtract);
        mallRefundRecordDetail.setRecordId(mallRefundRecord.getId());
        // 分析明细的归属跟随报表，重新生成时顺带修正历史 NULL 行
        mallRefundRecordDetail.setPlatformType(mallRefundRecord.getPlatformType());
        mallRefundRecordDetail.setShopId(mallRefundRecord.getShopId());
        mallRefundRecordDetail.insertOrUpdate();
        mallRefundRecord.setState(3);
        mallRefundRecord.updateById();
    }

    /** 比率计算：分母为 0 时返回 0 而非抛除零异常 */
    private static BigDecimal safeRate(BigDecimal numerator, BigDecimal denominator) {
        if (denominator == null || denominator.signum() == 0) {
            return BigDecimal.ZERO;
        }
        return numerator.divide(denominator, 4, RoundingMode.HALF_UP);
    }

    private static BigDecimal nvl(BigDecimal v) {
        return v == null ? BigDecimal.ZERO : v;
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
        detailWrapper.eq(MallRefundRecordDetail::getRecordId, id).last(SqlConstants.LIMIT_1);
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
                } else if (ORDER_STATUS_SUCCESS.equals(order.getOrderStatus())) {
                    successCount++;
                    successMoney = successMoney.add(order.getPayMoney() != null ? order.getPayMoney() : BigDecimal.ZERO);
                } else if (ORDER_STATUS_SHIPPED_WAIT.equals(order.getOrderStatus())) {
                    pendingCount++;
                }
            }
        }

        int unknownCount = totalCount - brushCount - successCount - refundCount - pendingCount;
        if (unknownCount < 0) unknownCount = 0;

        vo.setTotalPayAmount(totalPayAmount);
        vo.setProfitAmount(profitAmount);

        // 统计卡片（顺序：总订单数/补单单量/真实订单/退款订单/待定订单/未知订单）
        cards.add(buildCard(CARD_TYPE_TOTAL, "总订单数", totalCount, totalPayAmount, "#409eff", "Document"));
        cards.add(buildCard(CARD_TYPE_BRUSH, "补单单量", brushCount, brushMoney, "#e6a23c", "Warning"));
        cards.add(buildCard(CARD_TYPE_REAL, "真实订单", successCount, successMoney, "#67c23a", "CircleCheck"));
        cards.add(buildCard(CARD_TYPE_REFUND, "退款订单", refundCount, refundMoney, "#f56c6c", "CircleClose"));
        cards.add(buildCard(CARD_TYPE_PENDING, "待定订单", pendingCount, null, "#909399", "Question"));
        cards.add(buildCard(CARD_TYPE_UNKNOWN, "未知订单", unknownCount, null, "#9c27b0", "Question"));

        vo.setStatCards(cards);
        return vo;
    }

    private ReportStatCardVo buildCard(String cardType, String cardTitle, Integer count, BigDecimal amount, String color, String icon) {
        ReportStatCardVo card = new ReportStatCardVo();
        card.setCardType(cardType);
        card.setCardTitle(cardTitle);
        card.setCount(count);
        card.setAmount(amount);
        card.setColor(color);
        card.setIcon(icon);
        return card;
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
                orderType = CARD_TYPE_BRUSH;
                orderTypeDesc = "补单";
            } else if (order.getRefundMoney() != null && order.getRefundMoney().compareTo(BigDecimal.ZERO) > 0) {
                orderType = CARD_TYPE_REFUND;
                orderTypeDesc = "真实订单-退款";
            } else if (ORDER_STATUS_SUCCESS.equals(order.getOrderStatus())) {
                orderType = CARD_TYPE_REAL;
                orderTypeDesc = "真实订单";
            } else if (ORDER_STATUS_SHIPPED_WAIT.equals(order.getOrderStatus())) {
                orderType = CARD_TYPE_PENDING;
                orderTypeDesc = "真实订单-待定";
            } else {
                orderType = CARD_TYPE_UNKNOWN;
                orderTypeDesc = "未知";
            }
            vo.setOrderType(orderType);
            vo.setOrderTypeDesc(orderTypeDesc);

            // 关联货源订单
            vo.setSourceOrders(sourceOrderMap.getOrDefault(order.getOrderId(), Lists.newArrayList()));

            // 按卡片类型过滤
            if (StringUtils.isNotBlank(cardType)) {
                if (cardType.equals(CARD_TYPE_TOTAL)) {
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
