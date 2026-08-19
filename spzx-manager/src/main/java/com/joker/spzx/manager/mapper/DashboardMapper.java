package com.joker.spzx.manager.mapper;

import com.joker.spzx.model.vo.dashboard.OrderTrendVo;
import com.joker.spzx.model.vo.dashboard.PlatformDistVo;
import com.joker.spzx.model.vo.dashboard.RecentLogVo;
import com.joker.spzx.model.vo.dashboard.TopFactoryVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 仪表盘聚合查询 Mapper
 *
 * @author joker
 */
@Mapper
public interface DashboardMapper {

    @Select("SELECT COUNT(*) FROM order_info")
    Long countOrders();

    @Select("SELECT COALESCE(SUM(total_amount), 0) FROM order_info")
    java.math.BigDecimal sumOrderAmount();

    @Select("SELECT COUNT(*) FROM source_factory WHERE is_deleted = 0")
    Long countFactories();

    @Select("SELECT COUNT(*) FROM source_product WHERE is_deleted = 0")
    Long countProducts();

    @Select("SELECT DATE_FORMAT(create_time, '%Y-%m-%d') AS date, " +
            "COUNT(*) AS orderCount, COALESCE(SUM(total_amount), 0) AS orderAmount " +
            "FROM order_info GROUP BY DATE_FORMAT(create_time, '%Y-%m-%d') " +
            "ORDER BY date")
    List<OrderTrendVo> selectOrderTrend();

    @Select("SELECT platform_type AS platformType, COUNT(*) AS count " +
            "FROM source_product WHERE is_deleted = 0 GROUP BY platform_type")
    List<PlatformDistVo> selectPlatformDist();

    @Select("SELECT factory_name AS factoryName, total_sales AS totalSales, " +
            "quality_grade AS qualityGrade, category_name AS categoryName " +
            "FROM source_factory WHERE is_deleted = 0 " +
            "ORDER BY total_sales DESC LIMIT 10")
    List<TopFactoryVo> selectTopFactories();

    @Select("SELECT title, oper_name AS operName, create_time AS createTime " +
            "FROM sys_oper_log ORDER BY create_time DESC LIMIT 10")
    List<RecentLogVo> selectRecentLogs();

    @Select("SELECT item_id AS itemId, title, issue, mark_type AS markType, " +
            "suggest_category AS suggestCategory, create_time AS createTime " +
            "FROM taobao_1688_mark WHERE status = 0 AND mark_type IS NOT NULL " +
            "ORDER BY create_time DESC LIMIT 100")
    List<java.util.Map<String, Object>> selectWatermarkProducts();
}
