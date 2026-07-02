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
 * 商品和货源关系表
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Getter
@Setter
@TableName("mall_product_link")
@Schema(name = "MallProductLink", description = "商品和货源关系表")
public class MallProductLink extends Model<MallProductLink> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "工厂Id")
    @TableField("factory_Id")
    private String factoryId;

    @Schema(description = "货源链接地址")
    @TableField("product_id")
    private String productId;

    @TableField("is_currrent_delivery")
    private Integer isCurrrentDelivery;

    @Schema(description = "发货快递")
    @TableField("expresses")
    private String expresses;

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
