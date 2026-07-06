package com.joker.spzx.manager.service;

import com.joker.spzx.model.dto.system.WxLoginBindDto;
import com.joker.spzx.model.vo.system.WxLoginBindInfoVo;
import com.joker.spzx.model.vo.system.WxLoginCreateVo;
import com.joker.spzx.model.vo.system.WxLoginStatusVo;

public interface WxLoginService {

    WxLoginCreateVo createQrLogin(String clientIp);

    WxLoginStatusVo getQrLoginStatus(String ticket);

    String handleWxCallback(String code, String state);

    WxLoginStatusVo bindAccount(WxLoginBindDto dto, String clientIp);

    void unbind();

    WxLoginBindInfoVo getBindInfo();

    void cleanExpiredTickets();

    void mockScan(String ticket);

    void mockConfirm(String ticket);
}
