package com.joker.spzx.common.aspect;

import com.joker.spzx.common.annotation.Log;
import com.joker.spzx.common.service.AsyncOperLogService;
import com.joker.spzx.common.util.LogUtil;
import com.joker.spzx.model.entity.system.SysOperLog;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Aspect
@Component
@Slf4j
public class LogAspect {            // 环绕通知切面类定义
    @Autowired
    private AsyncOperLogService asyncOperLogService ;

    @Around(value = "@annotation(sysLog)")
    public Object doAroundAdvice(ProceedingJoinPoint joinPoint , Log sysLog) throws Throwable {
        // 构建前置参数
        SysOperLog sysOperLog = new SysOperLog() ;

        LogUtil.beforeHandleLog(sysLog , joinPoint , sysOperLog) ;

        Object proceed = null;
        try {
            proceed = joinPoint.proceed();
            // 执行业务方法
            LogUtil.afterHandlLog(sysLog , proceed , sysOperLog , 0 , null) ;
            // 构建响应结果参数
        } catch (Throwable e) {
            log.warn("操作执行异常, url={}", sysOperLog.getOperUrl(), e);
            LogUtil.afterHandlLog(sysLog, proceed, sysOperLog, 1, e.getMessage());
            throw e;
        } finally {
            // 成功与失败都要落审计日志（失败路径此前被丢失）
            try {
                asyncOperLogService.saveSysOperLog(sysOperLog);
            } catch (Exception e) {
                log.error("操作日志保存失败", e);
            }
        }

        // 返回执行结果
        return proceed ;                               // 返回执行结果
    }
}