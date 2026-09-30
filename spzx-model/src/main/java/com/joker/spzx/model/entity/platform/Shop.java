package com.joker.spzx.model.entity.platform;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 店铺注册表
 */
@Getter
@Setter
@TableName("shop")
@Schema(name = "Shop", description = "店铺注册表")
public class Shop {

    @Schema(description = "主键")
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;

    @Schema(description = "所属平台编码：1-淘宝, 2-抖音, 3-拼多多")
    @TableField("platform_code")
    private Integer platformCode;

    @Schema(description = "店铺名称")
    @TableField("shop_name")
    private String shopName;

    @Schema(description = "平台侧店铺ID")
    @TableField("outer_shop_id")
    private String outerShopId;

    @Schema(description = "数据采集通道：browser/api")
    @TableField("ingest_channel")
    private String ingestChannel;

    @Schema(description = "凭据引用（不含明文密钥）")
    @TableField("credential_ref")
    private String credentialRef;

    @Schema(description = "浏览器自动化 CDP 端口")
    @TableField("cdp_port")
    private Integer cdpPort;

    @Schema(description = "是否默认店铺：1-默认 0-普通")
    @TableField("is_default")
    private Integer isDefault;

    @Schema(description = "状态：1-启用 0-停用")
    @TableField("status")
    private Integer status;

    @Schema(description = "首次上架日期")
    @TableField("first_online_at")
    private LocalDate firstOnlineAt;

    @Schema(description = "创建时间")
    @TableField("create_time")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    @TableField("update_time")
    private LocalDateTime updateTime;
}
