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
 * 字典数据表
 * </p>
 *
 * @author joker
 * @since 2025-04-28 16:21:28
 */
@Getter
@Setter
@TableName("sys_dict_data")
@Schema(name = "SysDictData", description = "字典数据表")
public class SysDictData extends Model<SysDictData> {

    private static final long serialVersionUID = 1L;

    public static final Integer STATUS_NORMAL = 1;
    public static final Integer STATUS_DISABLED = 0;

    @Schema(description = "字典编码")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "字典排序")
    @TableField("dict_sort")
    private Integer dictSort;

    @Schema(description = "字典标签")
    @TableField("dict_label")
    private String dictLabel;

    @Schema(description = "字典键值")
    @TableField("dict_value")
    private String dictValue;

    @Schema(description = "字典类型")
    @TableField("dict_type")
    private String dictType;

    @Schema(description = "是否默认（Y是 N否）")
    @TableField("is_default")
    private String isDefault;

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
