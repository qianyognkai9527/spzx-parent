package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.mall.ItemOpsVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface ItemOpsMapper {

    /**
     * 商品运营台分页。
     *
     * @param facet  运营筛选项：all|noSale|negativeMargin|lowStock|noEffect|noSource
     * @param stock  低库存阈值，仅 lowStock 用
     * @param uvFrom 访客下限（含）
     */
    IPage<ItemOpsVo> pageItems(IPage<ItemOpsVo> page,
                               @Param("platformType") Integer platformType,
                               @Param("shopId") Long shopId,
                               @Param("keyword") String keyword,
                               @Param("facet") String facet,
                               @Param("stock") Integer stock,
                               @Param("uvFrom") Integer uvFrom);

    /**
     * 各筛选项在当前平台/店铺/关键词下的商品数。
     * 参数要和 pageItems 一致：base SQL 里的 where 用到它们，少一个会报 BindingException。
     */
    java.util.Map<String, Object> selectFacetCounts(@Param("platformType") Integer platformType,
                                                    @Param("shopId") Long shopId,
                                                    @Param("keyword") String keyword,
                                                    @Param("stock") Integer stock,
                                                    @Param("uvFrom") Integer uvFrom);
}
