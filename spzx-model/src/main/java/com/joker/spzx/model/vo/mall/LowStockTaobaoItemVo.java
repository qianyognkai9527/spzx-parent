package com.joker.spzx.model.vo.mall;

import lombok.Data;

/** taobao_offer_map 查询行：货源 -> 淘宝商品映射。 */
@Data
public class LowStockTaobaoItemVo {

    private Long sourceProductId;

    private Long taobaoItemId;

    private Long offerId;
}
