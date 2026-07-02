package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * <p>
 * 补单表
 * </p>
 *
 * @author joker
 * @since 2025-06-10 14:05:10
 */
@Data
@TableName("mall_add_order")
@Schema(name = "MallAddOrder", description = "补单表")
public class MallAddOrder extends Model<MallAddOrder> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "刷手Id")
    @TableField("brush_person_id")
    private Long brushPersonId;

    @Schema(description = "sku名称")
    @TableField("product_id")
    private String productId;

    @Schema(description = "淘宝订单号")
    @TableField("tb_order_id")
    private String tbOrderId;

    @Schema(description = "下单时间")
    @TableField("order_time")
    private LocalDateTime orderTime;

    @Schema(description = "订单状态")
    @TableField("order_state")
    private Integer orderState;

    @Schema(description = "本金")
    @TableField("seed_money")
    private Double seedMoney;

    @Schema(description = "佣金")
    @TableField("hire_money")
    private Double hireMoney;

    @Schema(description = "运费")
    @TableField("way_bill_money")
    private Double wayBillMoney;

    @Schema(description = "物流单号")
    @TableField("way_bill_code")
    private String wayBillCode;

    @Schema(description = "物流公司")
    @TableField("way_bill_name")
    private String wayBillName;

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

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
