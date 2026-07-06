package com.joker.spzx.manager.task;

import com.joker.spzx.manager.service.WxLoginService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class QrLoginTicketCleanTask {

    @Autowired
    private WxLoginService wxLoginService;

    @Scheduled(cron = "0 */5 * * * ?")
    public void cleanExpiredTickets() {
        try {
            wxLoginService.cleanExpiredTickets();
            log.info("过期扫码票据清理完成");
        } catch (Exception e) {
            log.error("清理过期扫码票据异常", e);
        }
    }
}
