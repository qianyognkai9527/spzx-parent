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
     * 「异常流量」判据，SQL 片段。与 mapper/ItemOpsMapper.xml 里 itemOpsBase 的同名片段必须逐字一致 ——
     * 首页趋势和商品运营台如果按两套口径剔流量，同一个商品在两页会给出互相矛盾的结论。
     * 改这里就要改那里，没有编译期约束兜住。
     */
    String ABNORMAL_TRAFFIC =
            "visitors >= 100 AND bounce_rate > 0.8 AND COALESCE(pay_byrs, 0) = 0";

    /**
     * 按生意参谋快照聚合的商品效果序列，快照时间倒序。
     *
     * 一个 point = 一次采集跑的 recent7 汇总，所以点与点之间是重叠的 7 日窗口，
     * 不是当日新增。按 snapshot_time 而不是按天分组：同一天跑两次会被日期分组加成两倍 GMV。
     *
     * 异常流量（ABNORMAL_TRAFFIC）单独摘出来，不进 visitors/cartUsers/payAmount：
     * 判据「访客≥100 且 跳失率>80% 且 近7日零成交」是 2026-10-05 拿库里 3,672 行反查定的 ——
     * 09-30 那次快照 14,966 访客里有 14,365 来自 16 件这种商品（跳失 97%~99%、零加购零搜索），
     * 而全库正常商品平均只有 3.2 个访客。最典型的一件（760216419668）09-14~27 是
     * 10 访客/1 成交/¥147，09-30 起变成 571 访客/0 成交/跳失 96.5%：同一件商品，流量涨了 57 倍
     * 而成交和加购一动不动，只能是平台侧灌进来的一次性低质流量，不是生意变好。
     * 剔掉的量同时返回给前端（abnormalItems/abnormalVisitors），界面要能说出剔了多少。
     */
    @Select("SELECT DATE_FORMAT(snapshot_time, '%Y-%m-%d %H:%i') AS snapshotTime, " +
            "COUNT(DISTINCT item_id) AS items, " +
            "COALESCE(SUM(CASE WHEN " + ABNORMAL_TRAFFIC + " THEN 0 ELSE visitors END), 0) AS visitors, " +
            "COALESCE(SUM(CASE WHEN " + ABNORMAL_TRAFFIC + " THEN 0 ELSE pay_amt END), 0) AS payAmount, " +
            "COALESCE(SUM(CASE WHEN " + ABNORMAL_TRAFFIC + " THEN 0 ELSE cart_users END), 0) AS cartUsers, " +
            "COALESCE(SUM(CASE WHEN " + ABNORMAL_TRAFFIC + " THEN 1 ELSE 0 END), 0) AS abnormalItems, " +
            "COALESCE(SUM(CASE WHEN " + ABNORMAL_TRAFFIC + " THEN visitors ELSE 0 END), 0) AS abnormalVisitors " +
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
