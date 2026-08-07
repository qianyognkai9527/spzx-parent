package com.joker.spzx.manager.job;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.manager.mapper.MerchantNotifyRecordMapper;
import com.joker.spzx.model.entity.pay.MerchantNotifyRecord;
import com.alibaba.fastjson.JSON;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
public class MerchantNotifyRetryJob {

    private static final int[] RETRY_INTERVALS_SECONDS = {0, 15, 60, 300, 600, 1800, 3600, 7200, 14400, 28800, 43200, 86400};
    private static final int MAX_RETRY = 15;

    @Autowired
    private MerchantNotifyRecordMapper notifyRecordMapper;
    @Autowired
    private OkHttpClient okHttpClient;

    @Scheduled(fixedDelay = 10000)
    public void execute() {
        List<MerchantNotifyRecord> pendingRecords = notifyRecordMapper.selectList(
            new LambdaQueryWrapper<MerchantNotifyRecord>()
                .eq(MerchantNotifyRecord::getNotifyStatus, 0)
                .le(MerchantNotifyRecord::getNextNotifyTime, LocalDateTime.now())
                .lt(MerchantNotifyRecord::getNotifyCount, MAX_RETRY));

        for (MerchantNotifyRecord record : pendingRecords) {
            sendNotify(record);
        }
    }

    private void sendNotify(MerchantNotifyRecord record) {
        int currentCount = (record.getNotifyCount() == null ? 0 : record.getNotifyCount()) + 1;
        boolean success = false;
        String responseContent = null;

        try {
            RequestBody body = RequestBody.create(
                record.getNotifyContent(),
                MediaType.parse("application/json; charset=utf-8"));
            Request request = new Request.Builder()
                .url(record.getNotifyUrl())
                .post(body)
                .build();
            try (Response response = okHttpClient.newCall(request).execute()) {
                success = response.isSuccessful();
                responseContent = response.body() != null ? response.body().string() : "";
            }
        } catch (Exception e) {
            responseContent = e.getMessage();
            log.error("商户通知重试失败 orderNo={}, count={}", record.getOrderNo(), currentCount, e);
        }

        LambdaUpdateWrapper<MerchantNotifyRecord> updateWrapper = new LambdaUpdateWrapper<MerchantNotifyRecord>()
            .eq(MerchantNotifyRecord::getId, record.getId())
            .set(MerchantNotifyRecord::getNotifyCount, currentCount)
            .set(MerchantNotifyRecord::getResponseContent, responseContent);

        if (success) {
            updateWrapper.set(MerchantNotifyRecord::getNotifyStatus, 1);
            log.info("商户通知成功 orderNo={}, count={}", record.getOrderNo(), currentCount);
        } else if (currentCount >= MAX_RETRY) {
            updateWrapper.set(MerchantNotifyRecord::getNotifyStatus, 2);
            log.warn("商户通知达到最大重试次数 orderNo={}, count={}", record.getOrderNo(), currentCount);
        } else {
            int intervalIdx = Math.min(currentCount, RETRY_INTERVALS_SECONDS.length - 1);
            LocalDateTime nextTime = LocalDateTime.now().plusSeconds(RETRY_INTERVALS_SECONDS[intervalIdx]);
            updateWrapper.set(MerchantNotifyRecord::getNextNotifyTime, nextTime);
        }

        notifyRecordMapper.update(null, updateWrapper);
    }
}
