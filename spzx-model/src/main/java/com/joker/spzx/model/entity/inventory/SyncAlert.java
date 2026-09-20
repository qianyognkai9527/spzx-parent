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

    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    private String alertType;

    private Long sourceProductId;

    private Long sourceSkuId;

    private Long platformProductId;

    private Long platformSkuId;

    private String oldValue;

    private String newValue;

    private String message;

    private Integer status;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @TableField("create_time")
    private LocalDateTime createTime;
}
