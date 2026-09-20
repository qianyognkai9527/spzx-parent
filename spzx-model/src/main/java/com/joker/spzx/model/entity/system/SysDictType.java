package com.joker.spzx.model.entity.system;

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
 * 字典类型表
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
@Getter
@Setter
@TableName("sys_dict_type")
@Schema(name = "SysDictType", description = "字典类型表")
public class SysDictType extends Model<SysDictType> {

    private static final long serialVersionUID = 1L;

    public static final Integer STATUS_NORMAL = 0;
    public static final Integer STATUS_DISABLED = 1;

    @Schema(description = "字典主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "字典名称")
    @TableField("dict_name")
    private String dictName;

    @Schema(description = "字典类型")
    @TableField("dict_type")
    private String dictType;

    @Schema(description = "状态（0正常 1停用）")
    @TableField("status")
    private Integer status;

    @Schema(description = "创建者")
    @TableField("create_by")
    private Long createBy;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新者")
    @TableField("update_by")
    private Long updateBy;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;

    @Schema(description = "备注")
    @TableField("remark")
    private String remark;

    @Override
    public Serializable pkVal() {
        return this.id;
    }
}
