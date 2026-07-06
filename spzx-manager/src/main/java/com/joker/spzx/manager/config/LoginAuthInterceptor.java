package com.joker.spzx.manager.config;

import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.joker.spzx.model.entity.system.SysUser;
import com.joker.spzx.model.vo.common.Result;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.utils.AuthContextUtil;
import com.joker.spzx.utils.Constant;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.concurrent.TimeUnit;

@Slf4j
@Component
public class LoginAuthInterceptor implements HandlerInterceptor {


    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        String requestMethod = request.getMethod();
        if (StringUtils.equalsIgnoreCase("OPTIONS", requestMethod)) {
            return true;
        }
        String requestURI = request.getRequestURI();
        if (Constant.isWhitePath(requestURI)) {
            return true;
        }

        String token = request.getHeader("token");
        if (StringUtils.isBlank(token)) {
            responseNoLoginInfo(response);
            log.warn("用户未登录，缺少token");
            return false;
        }
        String sysUserStr = redisTemplate.opsForValue().get("user:login:" + token);
        if (StringUtils.isBlank(sysUserStr)) {
            responseNoLoginInfo(response);
            log.warn("用户未登录，token无效");
            return false;
        }
        redisTemplate.expire("user:login:" + token, 7, TimeUnit.DAYS);

        SysUser sysUser = JSONObject.parseObject(sysUserStr, SysUser.class);
        AuthContextUtil.setUser(sysUser);

        return true;
    }

    //响应208状态码给前端
    private void responseNoLoginInfo(HttpServletResponse response) {
        Result<Object> result = Result.build(null, ResultCodeEnum.LOGIN_AUTH);
        PrintWriter writer = null;
        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json; charset=utf-8");
        try {
            writer = response.getWriter();
            writer.print(JSON.toJSONString(result));
        } catch (IOException e) {
            e.printStackTrace();
        } finally {
            if (writer != null) writer.close();
        }
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) throws Exception {
        AuthContextUtil.remove();
    }
}
