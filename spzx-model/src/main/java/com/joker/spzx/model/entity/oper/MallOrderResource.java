package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.io.Serializable;

/**
 * <p>
 * 订单与图片视频关联关系表
 * </p>
 *
 * @author joker
 * @since 2025-05-11 13:02:11
 */
@Data
@TableName("mall_order_resource")
@Schema(name = "MallOrderResource", description = "订单与图片视频关联关系表")
public class MallOrderResource extends Model<MallOrderResource> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "订单Id")
    @TableField("order_id")
    private Long orderId;

    @Schema(description = "关联资源Id")
    @TableField("file_id")
    private Long fileId;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
