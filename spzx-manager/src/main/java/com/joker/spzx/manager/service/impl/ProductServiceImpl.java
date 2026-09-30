package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductFactoryMapper;
import com.joker.spzx.manager.mapper.ProductDetailsMapper;
import com.joker.spzx.manager.mapper.ProductMapper;
import com.joker.spzx.manager.service.ProductService;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.model.dto.product.ProductDto;
import com.joker.spzx.model.entity.oper.MallProductFactory;
import com.joker.spzx.model.entity.product.Product;
import com.joker.spzx.model.entity.product.ProductDetails;
import com.joker.spzx.model.vo.product.ProductPageVo;
import com.joker.spzx.model.vo.product.Source1688Vo;
import com.joker.spzx.utils.AuthContextUtil;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.regex.Pattern;

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

    /** 1688 offerId 是纯数字；只按这个形状进数据库查询，链接里的其他部分一概不信 */
    private static final Pattern OFFER_ID_PATTERN = Pattern.compile("\\d{6,20}");

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

    /**
     * 采集数据陈旧阈值：collect_1688_full.py 是每周六全量，最坏情况跨过两个周末，
     * 超过 14 天就要求人工核对而不是静默采用。
     */
    static final int SOURCE_1688_STALE_DAYS = 14;

    @Override
    public Source1688Vo find1688ByOfferId(String offerId) {
        String code = offerId == null ? "" : offerId.trim();
        if (!OFFER_ID_PATTERN.matcher(code).matches()) {
            throw new ServiceException(500, "offerId 非法：只接受 6-20 位数字");
        }

        // source_product_code 就是链接里的 offerId（2367 行 URL 与 code 全等，走 idx_offer_code）。
        // 同一 offerId 可能因重复铺货存多行，取最后一次采集的那行；@TableLogic 已过滤 is_deleted。
        Product p = this.getOne(new LambdaQueryWrapper<Product>()
                .eq(Product::getSourceProductCode, code)
                .orderByDesc(Product::getUpdateTime)
                .last("LIMIT 1"), false);

        if (p == null) {
            return Source1688Vo.notCollected(code,
                    "该 1688 货源不在库里。后台不抓 1688（抓取只在 CDP 侧），"
                            + "请先在「货源商品」录入该链接，周六全量采集后即可带出货源价与运费；或本页手工填写。");
        }

        Integer daysAgo = p.getUpdateTime() == null ? null
                : (int) ChronoUnit.DAYS.between(p.getUpdateTime(), LocalDateTime.now());
        boolean stale = daysAgo == null || daysAgo > SOURCE_1688_STALE_DAYS;
        String hint = daysAgo == null ? "该货源行没有更新时间，价格请人工核对"
                : stale ? "采集于 " + daysAgo + " 天前，货源价/运费可能已变，建议重跑 collect_1688_full.py 后核对"
                : "采集于 " + daysAgo + " 天内，可直接采用";

        return new Source1688Vo(true, code, p.getId(), p.getSourceProductName(), p.getSourceProductUrl(),
                p.getSourcePrice(), p.getFreightCost(), p.getUpdateTime(), daysAgo, stale, hint);
    }

}
