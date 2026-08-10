package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductFactoryMapper;
import com.joker.spzx.manager.mapper.ProductDetailsMapper;
import com.joker.spzx.manager.mapper.ProductMapper;
import com.joker.spzx.manager.service.ProductService;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.oper.MallProductFactory;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.entity.product.ProductDetails;
import com.joker.spzx.model.entity.product.ProductSku;
import com.joker.spzx.model.vo.product.ProductPageVo;
import com.joker.spzx.utils.AuthContextUtil;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * <p>
 * 商品 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class ProductServiceImpl extends ServiceImpl<ProductMapper, Product> implements ProductService {

    @Resource
    private MallProductFactoryMapper mallProductFactoryMapper;

    @Resource
    private ProductDetailsMapper productDetailsMapper;

    @Override
    public IPage<ProductPageVo> findByPage(ProductDto productDto) {
        IPage<ProductPageVo> page = productDto.getPage();
        this.baseMapper.pageList(page, productDto);
        return page;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveData(Product product) {
        Long id = AuthContextUtil.getUser().getId();
        product.setIsDeleted(0);
        product.setCreateTime(LocalDateTime.now());
        product.setCreateBy(id);
        this.baseMapper.insert(product);

        Long productFactoryId = product.getProductFactoryId();
        if (productFactoryId != null) {
            MallProductFactory mallProductFactory = mallProductFactoryMapper.selectById(productFactoryId);
            if (mallProductFactory != null) {
                mallProductFactory.setDeployCount(mallProductFactory.getDeployCount() + 1);
                mallProductFactory.setUpdateBy(id);
                mallProductFactory.setUpdateTime(LocalDateTime.now());
                mallProductFactoryMapper.updateById(mallProductFactory);
            }
        }
    }

    @Override
    public ProductPageVo getDataById(Long id) {
        ProductPageVo product = this.baseMapper.getDetail(id);

        // 返回数据
        return product;
    }

    @Override
    public void updateDataById(Product product) {

        Long id = product.getId();
        Product productDb = this.getById(id);
        Long productFactoryIdDb = productDb != null ? productDb.getProductFactoryId() : null;
        Long productFactoryId = product.getProductFactoryId();
        Boolean isUpdateFactoryId = productFactoryId != null && !productFactoryId.equals(productFactoryIdDb);

        product.setUpdateBy(AuthContextUtil.getUser().getId());
        product.setUpdateTime(LocalDateTime.now());
        this.baseMapper.updateById(product);
        if (isUpdateFactoryId && productFactoryIdDb != null && productFactoryId != null) {
            MallProductFactory mallProductFactory = mallProductFactoryMapper.selectById(productFactoryIdDb);
            if (mallProductFactory != null) {
                mallProductFactory.setDeployCount(mallProductFactory.getDeployCount() - 1);
                mallProductFactoryMapper.updateById(mallProductFactory);
            }
            mallProductFactory = mallProductFactoryMapper.selectById(productFactoryId);
            if (mallProductFactory != null) {
                mallProductFactory.setDeployCount(mallProductFactory.getDeployCount() + 1);
                mallProductFactoryMapper.updateById(mallProductFactory);
            }
        }

    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteData(Long id) {
        Product product = new Product();
        product.setId(id);
        product.setIsDeleted(1);
        this.baseMapper.updateById(product);

        LambdaUpdateWrapper<ProductSku> set = new LambdaUpdateWrapper<ProductSku>()
                .eq(ProductSku::getProductId, id)
                .set(ProductSku::getIsDeleted, 1);
//        productSkuMapper.update(null, set);

        LambdaUpdateWrapper<ProductDetails> set1 = new LambdaUpdateWrapper<ProductDetails>()
                .eq(ProductDetails::getProductId, id)
                .set(ProductDetails::getIsDeleted, 1);
        productDetailsMapper.update(null, set1);

    }

}
