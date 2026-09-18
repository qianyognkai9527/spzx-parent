package com.joker.spzx.model.entity.kw;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.activerecord.Model;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("kw_config")
public class KwConfig extends Model<KwConfig> {

    @TableId(value = "config_key", type = IdType.INPUT)
    @TableField("config_key")
    private String configKey;

    @TableField("config_value")
    private String configValue;

    @TableField("update_time")
    private LocalDateTime updateTime;
}
