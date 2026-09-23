package com.joker.spzx.manager.service.videogen;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.manager.mapper.VideoGenTaskMapper;
import com.joker.spzx.model.entity.videogen.VideoGenTask;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/** 重启对账：非终态任务（线程池已丢）统一置 FAIL，前端可重试，轮询不再永动 */
@Slf4j
@Component
public class VideoGenStartupReconciler implements ApplicationRunner {
    @Autowired
    private VideoGenTaskMapper taskMapper;

    @Override
    public void run(ApplicationArguments args) {
        int n = taskMapper.update(null, new LambdaUpdateWrapper<VideoGenTask>()
                .set(VideoGenTask::getStatus, VideoGenTask.ST_FAIL)
                .set(VideoGenTask::getErrorMsg, "服务重启，任务中断")
                .set(VideoGenTask::getFinishTime, LocalDateTime.now())
                .in(VideoGenTask::getStatus, List.of(
                        VideoGenTask.ST_QUEUED, VideoGenTask.ST_SUBMITTED, VideoGenTask.ST_RUNNING)));
        if (n > 0) {
            log.info("videogen 启动对账：{} 个中断任务置为失败", n);
        }
    }
}
