package com.joker.spzx.model.entity.user;

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
 * 用户浏览记录表
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Getter
@Setter
@TableName("user_browse_history")
@Schema(name = "UserBrowseHistory", description = "用户浏览记录表")
public class UserBrowseHistory extends Model<UserBrowseHistory> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "用户ID")
    @TableField("user_id")
    private Long userId;

    @Schema(description = "商品skuID")
    @TableField("sku_id")
    private Long skuId;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;

    @TableField("is_deleted")
    private Byte isDeleted;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
