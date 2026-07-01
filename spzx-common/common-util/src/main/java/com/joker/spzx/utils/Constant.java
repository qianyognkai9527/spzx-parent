package com.joker.spzx.utils;

import org.springframework.util.AntPathMatcher;

import java.util.List;

public class Constant {

    private static final AntPathMatcher PATH_MATCHER = new AntPathMatcher();

    public static final List<String> whiteList = List.of(
            "/admin/system/index/login",
            "/admin/system/index/genVarifyCode",
            "/admin/system/fileUpload",
            "/js/**",
            "/css/**",
            "/img/**",
            "/fonts/**",
            "/index.html",
            "/favicon.ico",
            "/swagger-ui.html",
            "/webjars/**",
            "/swagger-resources/**",
            "/v3/**",
            "/api-docs/**",
            "/doc.html");

    /**
     * 判断请求路径是否在白名单中（支持 Ant 风格通配符匹配）
     */
    public static boolean isWhitePath(String requestUri) {
        for (String pattern : whiteList) {
            if (PATH_MATCHER.match(pattern, requestUri)) {
                return true;
            }
        }
        return false;
    }
}
