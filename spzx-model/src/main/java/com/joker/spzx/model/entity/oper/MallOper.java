package com.joker.spzx.model.entity.oper;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * <p>
 * 电商资源
 * </p>
 *
 * @author joker
 * @since 2025-04-23 23:33:23
 */
@Getter
@Setter
@TableName("mall_oper")
@Schema(name = "MallOper", description = "电商资源")
public class MallOper extends Model<MallOper> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "11位手机号")
    @TableField("mobile")
    private String mobile;

    @Schema(description = "优势")
    @TableField("merit")
    private String merit;

    @Schema(description = "头像")
    @TableField("avatar")
    private String avatar;

    @Schema(description = "微信Id")
    @TableField("wx_id")
    private String wxId;

    @Schema(description = "简称")
    @TableField("nick_name")
    private String nickName;

    @Schema(description = "全称")
    @TableField("full_name")
    private String fullName;

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

    @Schema(description = "1：买家秀 2：刷手")
    @TableField("type")
    private Integer type;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

    @Schema(description = "平台类型：1-淘宝, 2-抖音")
    @TableField("platform_type")
    private Integer platformType;

}
