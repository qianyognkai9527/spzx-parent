package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * <p>
 * 商品基本表
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Getter
@Setter
@TableName("platform_product")
@Schema(name = "MallProduct", description = "商品基本表")
public class MallProduct extends Model<MallProduct> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "商品编号")
    @TableField("code")
    private String code;

    @Schema(description = "当前标题")
    @TableField("title")
    private String title;

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

    @Schema(description = "定价")
    @TableField("pricing")
    private java.math.BigDecimal pricing;

    @Schema(description = "运费/邮费")
    @TableField("freight")
    private java.math.BigDecimal freight;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
