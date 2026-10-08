package com.joker.spzx.model.entity.promo;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 推广计划主档：计划元数据的权威录入处。
 *
 * 效果数据不在这张表里，仍在 promo_cost_daily / promo_cost_item_daily（按 campaign_id 关联）。
 * 这里刻意不存「最后有花费的日期」「累计花费」这类派生值 —— 存下来必然滞后，
 * 而滞后的数字在界面上看起来像事实。
 */
@Getter
@Setter
@TableName("promo_plan")
@Schema(name = "PromoPlan", description = "推广计划主档")
public class PromoPlan {

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "平台编码：1-淘宝, 2-抖音, 3-拼多多")
    @TableField("platform_code")
    private Integer platformCode;

    @Schema(description = "店铺 id，0=未指定")
    @TableField("shop_id")
    private Long shopId;

    @Schema(description = "平台侧计划 id，自然键")
    @TableField("campaign_id")
    private String campaignId;

    @Schema(description = "计划名称（改名以此处为准，历史花费行仍带旧名）")
    @TableField("campaign_name")
    private String campaignName;

    @Schema(description = "计划类型：keyword/crowd/site/other")
    @TableField("plan_type")
    private String planType;

    @Schema(description = "出价方式：custom_bid≈标准计划, roi_control≈智能控投产")
    @TableField("bid_type")
    private String bidType;

    @Schema(description = "日预算(元)")
    @TableField("daily_budget")
    private BigDecimal dailyBudget;

    @Schema(description = "关键词/人群出价基准(元)")
    @TableField("bid_price")
    private BigDecimal bidPrice;

    @Schema(description = "人群溢价百分数，30 表示 +30%")
    @TableField("premium_percent")
    private Integer premiumPercent;

    @Schema(description = "分时折扣描述")
    @TableField("time_discount")
    private String timeDiscount;

    @Schema(description = "投放开始日")
    @TableField("start_date")
    private LocalDate startDate;

    @Schema(description = "投放结束日，空=长期")
    @TableField("end_date")
    private LocalDate endDate;

    @Schema(description = "投放状态：null=未确认, 0=停投, 1=在投")
    @TableField("online_status")
    private Integer onlineStatus;

    @Schema(description = "负责人")
    @TableField("owner")
    private String owner;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

    @Schema(description = "来源：manual=后台录入, collected=从花费数据自动登记")
    @TableField("source")
    private String source;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;
}
