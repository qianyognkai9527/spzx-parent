package com.joker.spzx.model.vo.mall;

import lombok.Data;

import java.util.List;

/**
 * 低库存规格页一行 = 一个货源商品（source_product）。只读：数据由 automation/sourcing 链路维护。
 * taobaoItems/lowSpecs 由 service 在分组页查出后回填（三段式查询，避免 GROUP_CONCAT 截断）。
 */
@Data
public class LowStockRowVo {

    private Long sourceProductId;

    /** source_product_name；采集没给标题时前端回退显示 offer_id */
    private String title;

    /** 1688 货源页 URL */
    private String sourceUrl;

    /** 1688 offerId；无映射时为 null，前端显示「未匹配」 */
    private Long offerId;

    /** 关联淘宝商品 itemId 列表（一个货源挂多件是正常态） */
    private List<Long> taobaoItems;

    /** 该货源低库存规格的最低库存 */
    private Integer minStock;

    /** 低于阈值的规格数 */
    private Integer lowSpecCount;

    /** 低库存规格明细（按 stock 升序） */
    private List<LowStockSpecVo> lowSpecs;

    /** 人工处理标记：1=已下架 2=已删除 3=已下架SKU；未标记为 null（前端显示处理按钮） */
    private Integer handleType;

    /** 标记时间（SQL 里 DATE_FORMAT 成 'yyyy-MM-dd HH:mm'）；未标记为 null */
    private String handleTime;

    /** 货源存活：1=正常 0=已失效（前端失效徽标）；NULL=未检测 */
    private Integer sourceStatus;
}
