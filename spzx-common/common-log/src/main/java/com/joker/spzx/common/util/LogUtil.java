package com.joker.spzx.common.util;

import com.alibaba.fastjson.JSON;
import com.joker.spzx.common.annotation.Log;
import com.joker.spzx.model.entity.system.SysOperLog;
import com.joker.spzx.utils.AuthContextUtil;
import jakarta.servlet.http.HttpServletRequest;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.http.HttpMethod;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.regex.Pattern;

public class LogUtil {

    // JSON 形式: "password":"xxx"
    private static final Pattern PWD_JSON_PATTERN =
            Pattern.compile("(\"(?:password|passwd|pwd)\"\\s*:\\s*\")[^\"]*(\")", Pattern.CASE_INSENSITIVE);
    // toString 形式: password=xxx
    private static final Pattern PWD_TO_STRING_PATTERN =
            Pattern.compile("((?:password|passwd|pwd)\\s*=\\s*)[^,;\\]\\s]*", Pattern.CASE_INSENSITIVE);

    private static String maskSensitive(String text) {
        if (text == null) {
            return null;
        }
        return PWD_JSON_PATTERN.matcher(PWD_TO_STRING_PATTERN.matcher(text).replaceAll("$1***"))
                .replaceAll("$1***$2");
    }

    //操作执行之后调用
    public static void afterHandlLog(Log sysLog, Object proceed,
                                     SysOperLog sysOperLog, int status ,
                                     String errorMsg) {
        if(sysLog.isSaveResponseData()) {
            sysOperLog.setJsonResult(maskSensitive(JSON.toJSONString(proceed)));
        }
        sysOperLog.setStatus(status);
        sysOperLog.setErrorMsg(errorMsg);
    }

    //操作执行之前调用
    public static void beforeHandleLog(Log sysLog,
                                       ProceedingJoinPoint joinPoint,
                                       SysOperLog sysOperLog) {

        // 设置操作模块名称
        sysOperLog.setTitle(sysLog.title());
        sysOperLog.setOperatorType(sysLog.operatorType().name());

        // 获取目标方法信息
        MethodSignature methodSignature = (MethodSignature) joinPoint.getSignature() ;
        Method method = methodSignature.getMethod();
        sysOperLog.setMethod(method.getDeclaringClass().getName());

        // 获取请求相关参数
        ServletRequestAttributes requestAttributes = (ServletRequestAttributes)
                RequestContextHolder.getRequestAttributes();
        HttpServletRequest request = requestAttributes.getRequest();
        sysOperLog.setRequestMethod(request.getMethod());
        sysOperLog.setOperUrl(request.getRequestURI());
        sysOperLog.setOperIp(request.getRemoteAddr());

        // 设置请求参数
        if(sysLog.isSaveRequestData()) {
            String requestMethod = sysOperLog.getRequestMethod();
            if (HttpMethod.PUT.name().equals(requestMethod) || HttpMethod.POST.name().equals(requestMethod)) {
                String params = maskSensitive(Arrays.toString(joinPoint.getArgs()));
                sysOperLog.setOperParam(params);
            }
        }
        com.joker.spzx.model.entity.system.SysUser user = AuthContextUtil.getUser();
        sysOperLog.setOperName(user == null ? "anonymous" : user.getUsername());
    }
}