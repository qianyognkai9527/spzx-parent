package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.mall.ProductPicVideoDto;
import com.joker.spzx.model.entity.oper.MallProductPicVideo;

import java.util.List;

/**
 * <p>
 * 商品图片表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-05-02 20:52:02
 */
public interface MallProductPicVideoService extends IService<MallProductPicVideo> {

    void savePicVideo(ProductPicVideoDto productPicVideoDto);

    List<MallProductPicVideo> getPicVideo(Long productId, Long orderId, Integer platformType);
}
