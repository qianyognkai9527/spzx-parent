package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 仪表盘 KPI。
 *
 * 经营指标一律来自生意参谋商品效果快照（近 7 日滚动汇总），不是订单流水——
 * order_info 里只有 2023 年的联调数据，拿它算 GMV 会让首页第一屏就是假的。
 * snapshotAt + 口径说明必须随数据一起给到前端，避免把"近7日"读成"今日"。
 */
@Data
@Schema(description = "仪表盘KPI卡片数据")
public class DashboardKpiVo {

    @Schema(description = "近7日成交金额")
    private BigDecimal payAmount7d;

    @Schema(description = "近7日访客数")
    private Long visitors7d;

    @Schema(description = "近7日加购人数")
    private Long cartUsers7d;

    @Schema(description = "本次快照覆盖的商品数")
    private Integer effectItems;

    @Schema(description = "快照时间 yyyy-MM-dd HH:mm")
    private String snapshotAt;

    @Schema(description = "上一份快照的成交金额，用于环比；没有则为 null")
    private BigDecimal payAmountPrev7d;

    @Schema(description = "上一份快照的访客数")
    private Long visitorsPrev7d;

    @Schema(description = "本月支出合计")
    private BigDecimal monthExpense;

    @Schema(description = "本月支出台数")
    private Long monthExpenseCount;

    @Schema(description = "未读提醒数")
    private Long unreadAlerts;

    @Schema(description = "平台商品数（已登记在售，非生意参谋口径）")
    private Long platformProductCount;

    @Schema(description = "货源商品数")
    private Long productCount;

    @Schema(description = "货源工厂数")
    private Long factoryCount;
}
