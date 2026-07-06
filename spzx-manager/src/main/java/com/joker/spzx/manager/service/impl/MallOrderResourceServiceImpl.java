package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallOrderResourceMapper;
import com.joker.spzx.manager.service.MallOrderResourceService;
import com.joker.spzx.manager.service.MallProductPicVideoService;
import com.joker.spzx.model.entity.oper.MallOrderResource;
import com.joker.spzx.model.entity.oper.MallProductPicVideo;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.collections4.CollectionUtils;
import org.apache.commons.compress.utils.Lists;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * <p>
 * 订单与图片视频关联关系表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-05-11 13:02:11
 */
@Slf4j
@Service
public class MallOrderResourceServiceImpl extends ServiceImpl<MallOrderResourceMapper, MallOrderResource> implements MallOrderResourceService {

    @Autowired
    private MallProductPicVideoService mallProductPicVideoService;

    @Override
    public List<Long> getSelectResources(Long orderId) {
        LambdaQueryWrapper<MallOrderResource> eq = lambdaQuery().getWrapper().eq(MallOrderResource::getOrderId, orderId);
        List<MallOrderResource> list = list(eq);
        if (CollectionUtils.isEmpty(list)) {
            return Lists.newArrayList();
        }
        return list.stream().map(MallOrderResource::getFileId).collect(Collectors.toList());

    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void handInsert() {
        List<MallOrderResource> allResources = Lists.newArrayList();
        for (Long resourceId : new Long[]{82L, 83L, 84L, 85L, 86L}) {
            MallOrderResource r = new MallOrderResource();
            r.setOrderId(58L);
            r.setFileId(resourceId);
            allResources.add(r);
        }
        for (Long resourceId : new Long[]{87L, 88L, 89L}) {
            MallOrderResource r = new MallOrderResource();
            r.setOrderId(59L);
            r.setFileId(resourceId);
            allResources.add(r);
        }
        for (Long resourceId : new Long[]{90L, 91L, 92L}) {
            MallOrderResource r = new MallOrderResource();
            r.setOrderId(60L);
            r.setFileId(resourceId);
            allResources.add(r);
        }
        for (Long resourceId : new Long[]{93L, 94L, 95L}) {
            MallOrderResource r = new MallOrderResource();
            r.setOrderId(61L);
            r.setFileId(resourceId);
            allResources.add(r);
        }
        for (Long resourceId : new Long[]{96L, 97L, 98L}) {
            MallOrderResource r = new MallOrderResource();
            r.setOrderId(62L);
            r.setFileId(resourceId);
            allResources.add(r);
        }
        for (Long resourceId : new Long[]{99L, 100L, 101L, 102L, 103L}) {
            MallOrderResource r = new MallOrderResource();
            r.setOrderId(63L);
            r.setFileId(resourceId);
            allResources.add(r);
        }
        saveBatch(allResources);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void handInsert2() {
        LambdaQueryWrapper<MallOrderResource> gt = new LambdaQueryWrapper<MallOrderResource>()
                .gt(MallOrderResource::getId, 69L);
        List<MallOrderResource> list = this.list(gt);
        list.forEach(mallOrderResource -> {
            Long fileId = mallOrderResource.getFileId();
            String fileUrl = "http://127.0.0.1:9000/spzx-manager/20250515/" + fileId + ".jpg";
            LambdaQueryWrapper<MallProductPicVideo> queryWrapper = new LambdaQueryWrapper<MallProductPicVideo>()
                    .eq(MallProductPicVideo::getFileUrl, fileUrl)
                    .last(" limit 1");
            MallProductPicVideo obj = mallProductPicVideoService.getOne(queryWrapper);
            if (Objects.nonNull(obj)) {
                mallOrderResource.setFileId(obj.getId());
                mallOrderResource.updateById();
            } else {
                log.warn("文件地址查询失败：{}", mallOrderResource);
            }
        });
    }
}
