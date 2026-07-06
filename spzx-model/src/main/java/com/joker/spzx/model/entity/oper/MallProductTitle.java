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
 * 商品历史标题表
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Getter
@Setter
@TableName("platform_product_title")
@Schema(name = "MallProductTitle", description = "商品历史标题表")
public class MallProductTitle extends Model<MallProductTitle> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "产品编号")
    @TableField("product_id")
    private Long productId;

    @Schema(description = "历史标题")
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

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
