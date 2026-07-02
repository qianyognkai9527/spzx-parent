package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * <p>
 * 补单表
 * </p>
 *
 * @author joker
 * @since 2025-05-06 17:22:06
 */
@Data
@TableName("mall_farm_order")
@Schema(name = "MallFarmOrder", description = "补单表")
public class MallFarmOrder extends Model<MallFarmOrder> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "关联淘宝订单号")
    @TableField("tb_order_code")
    private String tbOrderCode;

    @Schema(description = "工厂链接地址")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "sku名称")
    @TableField("sku_name")
    private String skuName;

    @Schema(description = "刷单人Id(刷手或买家秀)")
    @TableField("shoot_person_id")
    private Long shootPersonId;

    @Schema(description = "本金")
    @TableField("seed_money")
    private Double seedMoney;

    @Schema(description = "佣金")
    @TableField("hire_money")
    private Double hireMoney;

    @Schema(description = "订单类型(1:付费刷手2:买家秀刷单3:商家互刷)")
    @TableField("order_type")
    private Integer orderType;

    @Schema(description = "刷单状态(1:创建 2:已拍单 3:物流到货4:已评价")
    @TableField("status")
    private Integer status;

    @Schema(description = "创建人")
    @TableField("create_by")
    private Long createBy;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新人")
    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "创建时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

    @Schema(description = "本金是否支付")
    @TableField("seed_is_pay")
    private Integer seedIsPay;

    @Schema(description = "佣金是否支付")
    @TableField("hire_is_pay")
    private Integer hireIsPay;

    @Schema(description = "评语")
    @TableField("comment")
    private String comment;

    @Schema(description = "评价状态")
    @TableField("comment_status")
    private Integer commentStatus;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;
}
