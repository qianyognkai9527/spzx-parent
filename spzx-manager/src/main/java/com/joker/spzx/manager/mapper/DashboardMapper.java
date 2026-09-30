package com.joker.spzx.manager.mapper;

import com.joker.spzx.model.vo.dashboard.EffectTrendVo;
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

    /**
     * 按生意参谋快照聚合的商品效果序列，快照时间倒序。
     *
     * 一个 point = 一次采集跑的 recent7 汇总，所以点与点之间是重叠的 7 日窗口，
     * 不是当日新增。按 snapshot_time 而不是按天分组：同一天跑两次会被日期分组加成两倍 GMV。
     */
    @Select("SELECT DATE_FORMAT(snapshot_time, '%Y-%m-%d %H:%i') AS snapshotTime, " +
            "COUNT(DISTINCT item_id) AS items, COALESCE(SUM(visitors), 0) AS visitors, " +
            "COALESCE(SUM(pay_amt), 0) AS payAmount, COALESCE(SUM(cart_users), 0) AS cartUsers " +
            "FROM sycm_item_effect_history " +
            "GROUP BY snapshot_time ORDER BY snapshot_time DESC LIMIT #{limit}")
    List<EffectTrendVo> selectEffectSnapshots(int limit);

    @Select("SELECT COUNT(*) FROM source_factory WHERE is_deleted = 0")
    Long countFactories();

    @Select("SELECT COUNT(*) FROM source_product WHERE is_deleted = 0")
    Long countProducts();

    @Select("SELECT COUNT(*) FROM platform_product")
    Long countPlatformProducts();

    @Select("SELECT COUNT(*) FROM sync_alert WHERE status = 0")
    Long countUnreadAlerts();

    @Select("SELECT COALESCE(SUM(amount), 0) FROM expense_order " +
            "WHERE expense_date >= DATE_FORMAT(CURDATE(), '%Y-%m-01')")
    java.math.BigDecimal sumMonthExpense();

    @Select("SELECT COUNT(*) FROM expense_order " +
            "WHERE expense_date >= DATE_FORMAT(CURDATE(), '%Y-%m-01')")
    Long countMonthExpense();

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
