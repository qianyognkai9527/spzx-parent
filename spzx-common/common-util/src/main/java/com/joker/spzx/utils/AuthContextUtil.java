package com.joker.spzx.utils;

import com.joker.spzx.model.entity.system.SysUser;

public class AuthContextUtil {

    private static final ThreadLocal<SysUser> threadLocal = new ThreadLocal<>();

    public static void setUser(SysUser user) {
        threadLocal.set(user);
    }

    public  static SysUser getUser(){
       return threadLocal.get();
    }

    public  static void remove(){
         threadLocal.remove();
    }
}
