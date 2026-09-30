package com.joker.spzx.model.dto.mall;


import com.joker.spzx.model.dto.system.PageParam;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

@Data
@Schema(description = "退款报表查询参数")
public class RefundReportPageDto extends PageParam {

    private String startDate;
    private String endDate;

    private String code;

    private Integer platformType;

    private Long shopId;

}
