package com.joker.spzx.model.vo.dashboard;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Schema(description = "最近操作日志")
public class RecentLogVo {

    @Schema(description = "操作模块")
    private String title;

    @Schema(description = "操作人")
    private String operName;

    @Schema(description = "操作时间")
    private LocalDateTime createTime;
}
