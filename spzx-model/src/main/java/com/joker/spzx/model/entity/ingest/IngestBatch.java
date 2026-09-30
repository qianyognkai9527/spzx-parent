package com.joker.spzx.model.entity.ingest;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 采集批次台账。写入方是 automation/ 下的 Python 脚本，Java 只读（洗数与新鲜度判定）。
 */
@Data
@TableName("ingest_batch")
public class IngestBatch {

    public static final String ST_QUEUED = "queued";
    public static final String ST_RUNNING = "running";
    public static final String ST_SUCCESS = "success";
    public static final String ST_PARTIAL = "partial";
    public static final String ST_FAILED = "failed";

    /** 计入「采集成功过」的状态：partial 是真数据已落、只是有脏行，不能当成没采 */
    public static final java.util.Set<String> LANDED = java.util.Set.of(ST_SUCCESS, ST_PARTIAL);

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("platform_code")
    private Integer platformCode;

    @TableField("shop_id")
    private Long shopId;

    @TableField("dataset")
    private String dataset;

    @TableField("channel")
    private String channel;

    /** 业务时间窗，不是抓取时间 */
    @TableField("biz_from")
    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate bizFrom;

    @TableField("biz_to")
    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate bizTo;

    @TableField("rows_total")
    private Integer rowsTotal;

    @TableField("rows_ok")
    private Integer rowsOk;

    @TableField("rows_dup")
    private Integer rowsDup;

    @TableField("rows_invalid")
    private Integer rowsInvalid;

    @TableField("status")
    private String status;

    @TableField("fingerprint")
    private String fingerprint;

    @TableField("error")
    private String error;

    @TableField("started_at")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime startedAt;

    @TableField("finished_at")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime finishedAt;

    @TableField("create_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @TableField("update_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
