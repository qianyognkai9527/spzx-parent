package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.vo.product.ProductPageVo;
import com.joker.spzx.model.vo.product.Source1688Vo;

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

    /**
     * 按 1688 offerId 回读已采集的货源行情（货源价/运费）。
     * 只读库、不抓取：抓 1688 依赖桌面 Chrome 登录态与 CDP 端口分工，属 Python 采集侧。
     * 未采集或数据陈旧都以 found=false / stale=true 的正常结果返回，不抛异常。
     */
    Source1688Vo find1688ByOfferId(String offerId);
}
