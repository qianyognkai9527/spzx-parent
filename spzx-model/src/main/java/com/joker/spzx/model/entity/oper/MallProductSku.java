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
 * 商品sku表
 * </p>
 *
 * @author joker
 * @since 2025-05-08 14:13:08
 */
@Getter
@Setter
@TableName("mall_product_sku")
@Schema(name = "MallProductSku", description = "商品sku表")
public class MallProductSku extends Model<MallProductSku> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "商品Id")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "sku名称")
    @TableField("sku_name")
    private String skuName;

    @Schema(description = "创建人")
    @TableField("create_by")
    private Long createBy;

    @Schema(description = "上下架状态")
    @TableField("status")
    private Integer status;

    @Schema(description = "删除标记")
    @TableField("del_flag")
    private Integer delFlag;

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
