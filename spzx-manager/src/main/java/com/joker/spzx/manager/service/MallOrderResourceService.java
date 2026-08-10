package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.entity.oper.MallOrderResource;

import java.util.List;

/**
 * <p>
 * 订单与图片视频关联关系表 服务类
 * </p>
 *
 * @author joker
 * @since 2025-05-11 13:02:11
 */
public interface MallOrderResourceService extends IService<MallOrderResource> {

    List<Long> getSelectResources(Long productId);

}
