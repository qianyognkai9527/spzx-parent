package com.joker.spzx.model.dto.product;

import com.joker.spzx.model.dto.system.PageParam;
import lombok.Data;


@Data
public class UserCostPageDto extends PageParam {

    private Integer billType;
    private Integer payType;
    private Integer payUsageId;

    private Integer platformType;
}
