package com.joker.spzx.model.entity.videogen;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("video_gen_task")
public class VideoGenTask extends Model<VideoGenTask> {

    public static final int ST_QUEUED = 0, ST_SUBMITTED = 1, ST_RUNNING = 2, ST_DONE = 3, ST_FAIL = 4;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("product_id")
    private Long productId;

    @TableField("prompt")
    private String prompt;

    @TableField("prompt_source")
    private Integer promptSource;

    @TableField("model")
    private String model;

    @TableField("duration")
    private Integer duration;

    @TableField("ratio")
    private String ratio;

    @TableField("est_cost")
    private BigDecimal estCost;

    @TableField("status")
    private Integer status;

    @TableField("remote_task_id")
    private String remoteTaskId;

    @TableField("object_key")
    private String objectKey;

    @TableField("error_msg")
    private String errorMsg;

    @TableField("finish_time")
    private LocalDateTime finishTime;

    @TableField("create_by")
    private Long createBy;

    @TableField("create_time")
    private LocalDateTime createTime;

    @TableField("update_time")
    private LocalDateTime updateTime;

    @TableLogic
    @TableField("is_deleted")
    private Integer isDeleted;
}
