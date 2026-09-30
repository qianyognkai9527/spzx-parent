package com.joker.spzx.model.entity.ingest;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 采集原始报文：洗数前留档，平台改字段时改映射器重放即可，不必重抓。
 */
@Data
@TableName("ingest_raw")
public class IngestRaw {

    public static final String ST_PENDING = "pending";
    public static final String ST_NORMALIZED = "normalized";
    public static final String ST_INVALID = "invalid";

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @TableField("batch_id")
    private Long batchId;

    @TableField("natural_key")
    private String naturalKey;

    /** JSON 列，Python 写入原文，Java 侧按映射器解析 */
    @TableField("payload")
    private String payload;

    @TableField("fingerprint")
    private String fingerprint;

    @TableField("status")
    private String status;

    @TableField("error")
    private String error;

    @TableField("create_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @TableField("update_time")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
