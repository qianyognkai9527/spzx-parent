package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.vo.product.ProductPageVo;

/**
 * <p>
 * 商品 服务类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
public interface ProductService extends IService<Product> {

    IPage<ProductPageVo> findByPage(ProductDto productDto);

    void saveData(Product product);

    ProductPageVo getDataById(Long id);

    void updateDataById(Product product);

    void deleteData(Long id);
}
