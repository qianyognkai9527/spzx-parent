package com.joker.spzx.model.dto.mall;


import com.joker.spzx.model.dto.system.PageParam;
import lombok.Data;

import java.util.Date;

@Data
public class MallAddOrderPageDto extends PageParam {

    private Long brushId;
    private String tbOrderId;
    private Integer orderstate;
    private Date createTimeStart;

    private Date createTimeEnd;

    private Integer platformType;


}
