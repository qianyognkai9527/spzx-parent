package com.joker.spzx.model.entity.inventory;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 库存同步提醒
 */
@Data
@TableName("sync_alert")
public class SyncAlert {

    public static final Integer STATUS_UNREAD = 0;
    public static final Integer STATUS_READ = 1;
    /** 告警条件已自愈，由系统关闭：不进未读列表，行留着可审计 */
    public static final Integer STATUS_RESOLVED = 2;

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String alertType;

    /**
     * 采集契约类告警（alert_type=ingest_stale）所属数据集 code。
     * 没有这一列，恢复新鲜时 Java 侧认不出哪条未读提醒属于哪个数据集，
     * 过期告警就会在数据早已追平的情况下继续挂在看板上。
     */
    @TableField("dataset_code")
    private String datasetCode;

    private Long sourceProductId;

    private Long sourceSkuId;

    private Long platformProductId;

    private Long platformSkuId;

    private String oldValue;

    private String newValue;

    private String message;

    private Integer status;

    /** 外部告警通道（钉钉 webhook）是否已推送，由 SyncAlertNotifyTask 维护 */
    private Integer notified;

    /** 所属店铺 */
    @TableField("shop_id")
    private Long shopId;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @TableField("create_time")
    private LocalDateTime createTime;
}
