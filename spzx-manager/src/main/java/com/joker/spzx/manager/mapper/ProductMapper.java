package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.vo.product.ProductPageVo;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * <p>
 * 商品 Mapper 接口
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Mapper
public interface ProductMapper extends BaseMapper<Product> {

    IPage<ProductPageVo> pageList(@Param("page") IPage<ProductPageVo> page, @Param("productDto") ProductDto productDto);

    ProductPageVo getDetail(Long id);
}
