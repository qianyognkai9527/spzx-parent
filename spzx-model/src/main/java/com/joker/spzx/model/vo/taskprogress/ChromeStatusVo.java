package com.joker.spzx.model.vo.taskprogress;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "Chrome 实例资源状态")
public class ChromeStatusVo {

    @Schema(description = "CDP端口")
    private Integer port;

    @Schema(description = "Chrome是否运行")
    private Boolean running;

    @Schema(description = "标签页数量")
    private Integer tabs;

    @Schema(description = "内存 RSS (MB)")
    private Integer rssMB;

    @Schema(description = "CPU 使用率 (%)")
    private Double cpuPercent;

    @Schema(description = "描述信息")
    private String desc;
}
