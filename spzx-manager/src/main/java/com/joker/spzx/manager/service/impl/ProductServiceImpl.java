package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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
        product.setCreateBy(id);
        this.baseMapper.insert(product);

        Long productFactoryId = product.getProductFactoryId();
        if (productFactoryId != null) {
            adjustDeployCount(productFactoryId, 1, id);
        }
    }

    /** 原子增减铺货计数，避免并发下的丢失更新（delta 仅代码内常量字面量） */
    private void adjustDeployCount(Long factoryId, int delta, Long userId) {
        if (factoryId == null) {
            return;
        }
        mallProductFactoryMapper.update(null, new LambdaUpdateWrapper<MallProductFactory>()
                .setSql("deploy_count = GREATEST(COALESCE(deploy_count, 0) + (" + delta + "), 0)")
                .set(MallProductFactory::getUpdateBy, userId)
                .set(MallProductFactory::getUpdateTime, LocalDateTime.now())
                .eq(MallProductFactory::getId, factoryId));
    }

    @Override
    public ProductPageVo getDataById(Long id) {
        ProductPageVo product = this.baseMapper.getDetail(id);

        // 返回数据
        return product;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateDataById(Product product) {

        Long id = product.getId();
        Product productDb = this.getById(id);
        Long productFactoryIdDb = productDb != null ? productDb.getProductFactoryId() : null;
        Long productFactoryId = product.getProductFactoryId();
        Boolean isUpdateFactoryId = productFactoryId != null && !productFactoryId.equals(productFactoryIdDb);

        product.setUpdateBy(AuthContextUtil.getUser().getId());
        this.baseMapper.updateById(product);
        if (isUpdateFactoryId && productFactoryIdDb != null && productFactoryId != null) {
            Long uid = AuthContextUtil.getUser().getId();
            adjustDeployCount(productFactoryIdDb, -1, uid);
            adjustDeployCount(productFactoryId, 1, uid);
        }

    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteData(Long id) {
        this.removeById(id);

        LambdaQueryWrapper<ProductDetails> detailsWrapper = new LambdaQueryWrapper<ProductDetails>()
                .eq(ProductDetails::getProductId, id);
        productDetailsMapper.delete(detailsWrapper);

    }

}
