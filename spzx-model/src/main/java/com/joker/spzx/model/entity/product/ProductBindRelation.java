package com.joker.spzx.model.entity.product;

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
 * 商品属性表
 * </p>
 *
 * @author joker
 * @since 2025-08-22 15:59:22
 */
@Getter
@Setter
@TableName("product_bind_relation")
@Schema(name = "ProductBindRelation", description = "商品属性表")
public class ProductBindRelation extends Model<ProductBindRelation> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "ID")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "商品id")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "货源商品Id")
    @TableField("source_productId")
    private Long sourceProductid;

    @Schema(description = "属性value")
    @TableField("create_by")
    private Long createBy;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "删除标记（0:不可用 1:可用）")
    @TableField("is_deleted")
    private Integer isDeleted;

    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField(exist = false)
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
