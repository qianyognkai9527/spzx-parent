package com.joker.spzx.manager.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.joker.spzx.model.dto.product.SourceFactoryPageParam;
import com.joker.spzx.model.entity.product.SourceFactory;

import java.util.List;

/**
 * <p>
 * 爬虫工厂排行榜 服务接口
 * </p>
 *
 * @author joker
 */
public interface SourceFactoryService extends IService<SourceFactory> {

    IPage<SourceFactory> pageList(SourceFactoryPageParam pageParam);

    void saveData(SourceFactory sourceFactory);

    void updateData(SourceFactory sourceFactory);

    List<SourceFactory> getAll(Integer platformType);

    List<SourceFactory> exportList(SourceFactoryPageParam pageParam);

    void deleteById(Long id);
}
