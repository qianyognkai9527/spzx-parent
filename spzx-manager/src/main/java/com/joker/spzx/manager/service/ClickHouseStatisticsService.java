package com.joker.spzx.manager.service;

import com.joker.spzx.model.dto.order.OrderStatisticsDto;
import com.joker.spzx.model.vo.order.OrderStatisticsVo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@ConditionalOnProperty(name = "app.enable-infra", havingValue = "true")
public class ClickHouseStatisticsService {

    @Autowired
    @Qualifier("clickHouseJdbcTemplate")
    private JdbcTemplate clickHouseJdbcTemplate;

    public OrderStatisticsVo getOrderStatistics(OrderStatisticsDto dto) {
        StringBuilder sql = new StringBuilder(
                "SELECT order_date, total_amount FROM spzx_analytics.order_statistics WHERE is_deleted = 0");

        List<Object> params = new ArrayList<>();
        if (dto.getPlatformType() != null) {
            sql.append(" AND platform_type = ?");
            params.add(dto.getPlatformType());
        }
        if (dto.getCreateTimeBegin() != null && !dto.getCreateTimeBegin().isEmpty()) {
            sql.append(" AND order_date >= ?");
            params.add(dto.getCreateTimeBegin());
        }
        if (dto.getCreateTimeEnd() != null && !dto.getCreateTimeEnd().isEmpty()) {
            sql.append(" AND order_date <= ?");
            params.add(dto.getCreateTimeEnd());
        }
        sql.append(" ORDER BY order_date");

        List<Map<String, Object>> rows = clickHouseJdbcTemplate.queryForList(
                sql.toString(), params.toArray());

        List<String> dateList = new ArrayList<>();
        List<BigDecimal> amountList = new ArrayList<>();

        for (Map<String, Object> row : rows) {
            dateList.add(String.valueOf(row.get("order_date")));
            amountList.add((BigDecimal) row.get("total_amount"));
        }

        OrderStatisticsVo vo = new OrderStatisticsVo();
        vo.setDateList(dateList);
        vo.setAmountList(amountList);
        return vo;
    }
}