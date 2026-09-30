package com.joker.spzx.model.entity.ingest;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 采集数据集契约与新鲜度状态。Java 侧拥有契约与告警状态，Python 只写 ingest_batch/ingest_raw。
 */
@Data
@TableName("ingest_dataset")
public class IngestDataset {

    public static final String MEASURE_TABLE = "table";
    public static final String MEASURE_BATCH = "batch";

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    /** 数据集编码，全局唯一，与 ingest_batch.dataset 对齐 */
    @TableField("code")
    private String code;

    @TableField("name")
    private String name;

    /** 归属平台码，null=跨平台上游（1688 货源） */
    @TableField("platform_code")
    private Integer platformCode;

    /** table=读事实表时间列；batch=读 ingest_batch 成功时间 */
    @TableField("measure")
    private String measure;

    @TableField("target_table")
    private String targetTable;

    @TableField("freshness_col")
    private String freshnessCol;

    @TableField("natural_key_cols")
    private String naturalKeyCols;

    @TableField("required_cols")
    private String requiredCols;

    @TableField("sla_hours")
    private Integer slaHours;

    /** 0=无自动写入方，不参与告警 */
    @TableField("monitor")
    private Integer monitor;

    @TableField("writer")
    private String writer;

    @TableField("cron_expr")
    private String cronExpr;

    /** 本轮过期起点，恢复新鲜后置 null */
    @TableField("stale_since")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime staleSince;

    /** 本轮过期已推送告警时间，与 staleSince 比较实现一轮只告一次 */
    @TableField("alerted_at")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime alertedAt;

    @TableField("remark")
    private String remark;

    @TableField("create_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @TableField("update_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
