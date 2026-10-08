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
 * 日程任务表
 * </p>
 *
 * @author joker
 * @since 2025-05-20 11:34:20
 */
@Getter
@Setter
@TableName("sys_user_schedule_task")
@Schema(name = "SysUserScheduleTask", description = "日程任务表")
public class SysUserScheduleTask extends Model<SysUserScheduleTask> {

    private static final long serialVersionUID = 1L;

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "日程Id")
    @TableField("schedule_id")
    private Long scheduleId;

    @Schema(description = "任务标题")
    @TableField("task_title")
    private String taskTitle;

    @Schema(description = "任务模块（自由文本，AI 留痕用）")
    @TableField("module")
    private String module;

    @Schema(description = "排序值")
    @TableField("sort")
    private Integer sort;

    @Schema(description = "完成比例")
    @TableField("complete_ratio")
    private Integer completeRatio;

    @Schema(description = "是否完成")
    @TableField("is_complete")
    private Integer isComplete;

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
