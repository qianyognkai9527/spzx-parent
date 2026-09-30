package com.joker.spzx.manager.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.joker.spzx.model.entity.ingest.IngestBatch;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface IngestBatchMapper extends BaseMapper<IngestBatch> {
}
