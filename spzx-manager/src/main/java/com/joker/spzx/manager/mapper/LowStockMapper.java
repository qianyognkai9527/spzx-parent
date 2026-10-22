package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.vo.mall.LowStockRowVo;
import com.joker.spzx.model.vo.mall.LowStockSpecVo;
import com.joker.spzx.model.vo.mall.LowStockTaobaoItemVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 低库存规格页查询 + 人工处理标记（low_stock_handle：1=已下架 2=已删除 3=已下架SKU）。
 * 库存/映射数据由 automation/sourcing 维护，这里不碰；标记是唯一写入，页面按钮只是留痕。
 */
@Mapper
public interface LowStockMapper {

    /** 分组的货源页：只算 minStock/lowSpecCount，映射与明细由另两条按页内 id 补齐 */
    IPage<LowStockRowVo> selectLowStockGroups(IPage<LowStockRowVo> page,
                                              @Param("threshold") int threshold,
                                              @Param("keyword") String keyword,
                                              @Param("handleStatus") String handleStatus);

    List<LowStockTaobaoItemVo> selectTaobaoItems(@Param("ids") List<Long> ids);

    List<LowStockSpecVo> selectLowSpecs(@Param("ids") List<Long> ids,
                                        @Param("threshold") int threshold);

    /** 货源失效视图：source_status=0 的铺货货源（无 SKU 行也能进列表），lowSpecCount 恒 0 */
    IPage<LowStockRowVo> selectDeadGroups(IPage<LowStockRowVo> page,
                                          @Param("keyword") String keyword,
                                          @Param("handleStatus") String handleStatus);

    /** 同一货源重复标记原地覆盖（UPSERT）；handleTime 由 SQL NOW() 生成 */
    int upsertHandle(@Param("sourceProductId") Long sourceProductId,
                     @Param("handleType") Integer handleType,
                     @Param("handleBy") Long handleBy);

    /** 撤销标记 = 删行 */
    int clearHandle(@Param("sourceProductId") Long sourceProductId);
}
