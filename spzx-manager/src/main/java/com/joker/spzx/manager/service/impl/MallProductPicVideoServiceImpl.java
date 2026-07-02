package com.joker.spzx.manager.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.manager.mapper.MallProductPicVideoMapper;
import com.joker.spzx.manager.service.MallProductPicVideoService;
import com.joker.spzx.model.dto.mall.PicVideoSimplerDto;
import com.joker.spzx.model.dto.mall.ProductPicVideoDto;
import com.joker.spzx.model.entity.oper.MallProductPicVideo;
import com.joker.spzx.utils.AuthContextUtil;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * <p>
 * 商品图片表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-05-02 20:52:02
 */
@Service
public class MallProductPicVideoServiceImpl extends ServiceImpl<MallProductPicVideoMapper, MallProductPicVideo> implements MallProductPicVideoService {

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void savePicVideo(ProductPicVideoDto productPicVideoDto) {

        Long productId = productPicVideoDto.getProductId();
        Long operId = productPicVideoDto.getOperId();
        String takeDate = productPicVideoDto.getTakeDate();
        Long userId = AuthContextUtil.getUser().getId();
        List<PicVideoSimplerDto> picVideoSimplerDtoList = productPicVideoDto.getPicVideoSimplerDtoList();
        List<MallProductPicVideo> collect = picVideoSimplerDtoList.stream().map(picVideoSimplerDto -> {
            MallProductPicVideo mallProductPicVideo = new MallProductPicVideo();
            mallProductPicVideo.setProductId(productId);
            mallProductPicVideo.setPersonId(operId);
            mallProductPicVideo.setCreateBy(userId);
            mallProductPicVideo.setCreateTime(LocalDateTime.now());
            mallProductPicVideo.setState(0);
            String fileName = picVideoSimplerDto.getFileName();
            mallProductPicVideo.setFileName(fileName);
            mallProductPicVideo.setFileUrl(picVideoSimplerDto.getFileUrl());
            mallProductPicVideo.setFileType(fileName.matches(".*\\.(jpg|png|gif|jpeg|bmp)$") ? 1 : 2);
            mallProductPicVideo.setTakeDate(takeDate);
            mallProductPicVideo.setPlatformType(productPicVideoDto.getPlatformType());

            return mallProductPicVideo;
        }).collect(Collectors.toList());
        this.saveBatch(collect);

    }

    @Override
    public List<MallProductPicVideo> getPicVideo(Long productId, Long orderId, Integer platformType) {
        LambdaQueryWrapper<MallProductPicVideo> eq = lambdaQuery().getWrapper()
                .eq(MallProductPicVideo::getPlatformType, platformType)
                .eq(MallProductPicVideo::getProductId, productId)
                .eq(MallProductPicVideo::getState, 0)
                .orderByDesc(MallProductPicVideo::getTakeDate)
                .orderByAsc(MallProductPicVideo::getFileName);
        List<MallProductPicVideo> list = list(eq);
        if (Objects.isNull(orderId)) {
            return list;
        }
        List<MallProductPicVideo> selectedPicVideos = this.baseMapper.selectPicVideoListByOrderId(orderId);
        selectedPicVideos.addAll(list);
        return selectedPicVideos;
    }
}
