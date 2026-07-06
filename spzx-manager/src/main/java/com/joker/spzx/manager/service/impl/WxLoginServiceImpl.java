package com.joker.spzx.manager.service.impl;

import cn.hutool.http.HttpUtil;
import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.config.WxLoginProperties;
import com.joker.spzx.manager.mapper.SysLoginLogMapper;
import com.joker.spzx.manager.mapper.SysQrLoginTicketMapper;
import com.joker.spzx.manager.mapper.SysUserMapper;
import com.joker.spzx.manager.mapper.SysWechatUserMapper;
import com.joker.spzx.manager.service.WxLoginService;
import com.joker.spzx.model.dto.system.WxLoginBindDto;
import com.joker.spzx.model.entity.system.SysLoginLog;
import com.joker.spzx.model.entity.system.SysQrLoginTicket;
import com.joker.spzx.model.entity.system.SysUser;
import com.joker.spzx.model.entity.system.SysWechatUser;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.system.WxLoginBindInfoVo;
import com.joker.spzx.model.vo.system.WxLoginCreateVo;
import com.joker.spzx.model.vo.system.WxLoginStatusVo;
import com.joker.spzx.utils.AuthContextUtil;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.util.DigestUtils;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class WxLoginServiceImpl implements WxLoginService {

    private static final String QR_REDIS_PREFIX = "qr:login:";
    private static final String USER_LOGIN_REDIS_PREFIX = "user:login:";

    @Autowired
    private WxLoginProperties wxLoginProperties;

    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Autowired
    private SysWechatUserMapper sysWechatUserMapper;

    @Autowired
    private SysQrLoginTicketMapper sysQrLoginTicketMapper;

    @Autowired
    private SysLoginLogMapper sysLoginLogMapper;

    @Autowired
    private SysUserMapper sysUserMapper;

    @Override
    public WxLoginCreateVo createQrLogin(String clientIp) {
        String ticket = UUID.randomUUID().toString().replace("-", "");
        String state = UUID.randomUUID().toString().replace("-", "");

        JSONObject qrData = new JSONObject();
        qrData.put("status", 0);
        qrData.put("state", state);
        qrData.put("createTime", System.currentTimeMillis());

        redisTemplate.opsForValue().set(
                QR_REDIS_PREFIX + ticket,
                qrData.toJSONString(),
                wxLoginProperties.getQrTtlSeconds(),
                TimeUnit.SECONDS
        );

        saveTicketAsync(ticket, state, clientIp);

        String wxAuthUrl;
        if (Boolean.TRUE.equals(wxLoginProperties.getMockMode())) {
            wxAuthUrl = wxLoginProperties.getMockBaseUrl()
                    + "/admin/system/index/wxLogin/mockConfirm?ticket=" + ticket;
        } else {
            wxAuthUrl = wxLoginProperties.getAuthUrl()
                    + "?appid=" + wxLoginProperties.getAppId()
                    + "&redirect_uri=" + URLEncoder.encode(wxLoginProperties.getRedirectUri(), StandardCharsets.UTF_8)
                    + "&response_type=code"
                    + "&scope=snsapi_login"
                    + "&state=" + state
                    + "#wechat_redirect";
        }

        WxLoginCreateVo vo = new WxLoginCreateVo();
        vo.setTicket(ticket);
        vo.setWxAuthUrl(wxAuthUrl);
        return vo;
    }

    @Override
    public WxLoginStatusVo getQrLoginStatus(String ticket) {
        String key = QR_REDIS_PREFIX + ticket;
        String qrJson = redisTemplate.opsForValue().get(key);

        WxLoginStatusVo vo = new WxLoginStatusVo();
        vo.setTicket(ticket);

        if (StringUtils.isBlank(qrJson)) {
            vo.setStatus(3);
            vo.setMessage("二维码已过期，请刷新");
            return vo;
        }

        JSONObject qrData = JSON.parseObject(qrJson);
        Integer status = qrData.getInteger("status");
        vo.setStatus(status);

        switch (status) {
            case 0:
                vo.setMessage("请使用微信扫码登录");
                break;
            case 1:
                vo.setMessage("已扫描，请在手机上确认");
                break;
            case 2:
                vo.setMessage("登录成功");
                vo.setToken(qrData.getString("token"));
                redisTemplate.delete(key);
                break;
            case 4:
                vo.setMessage("已取消");
                break;
            case 5:
                vo.setMessage("请绑定本地账号");
                break;
            default:
                vo.setMessage("未知状态");
                break;
        }
        return vo;
    }

    @Override
    public String handleWxCallback(String code, String state) {
        String html = "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body style='text-align:center;padding-top:50px'><h3>处理中，请稍候...</h3></body></html>";

        if (StringUtils.isBlank(code) || StringUtils.isBlank(state)) {
            log.warn("微信回调参数为空: code={}, state={}", code, state);
            return html;
        }

        String ticket = findTicketByState(state);
        if (StringUtils.isBlank(ticket)) {
            log.warn("微信回调state未找到对应票据: state={}", state);
            return html;
        }

        String qrKey = QR_REDIS_PREFIX + ticket;
        String qrJson = redisTemplate.opsForValue().get(qrKey);
        if (StringUtils.isBlank(qrJson)) {
            log.warn("微信回调票据已过期: ticket={}", ticket);
            return html;
        }

        JSONObject qrData = JSON.parseObject(qrJson);
        Integer currentStatus = qrData.getInteger("status");
        if (currentStatus != null && currentStatus >= 2) {
            log.info("票据已处理过，幂等返回: ticket={}, status={}", ticket, currentStatus);
            return html;
        }

        qrData.put("status", 1);
        redisTemplate.opsForValue().set(qrKey, qrData.toJSONString(),
                wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);

        JSONObject tokenResult = getWxAccessToken(code);
        if (tokenResult == null) {
            log.error("获取微信access_token失败: code={}", code);
            return html;
        }

        String openid = tokenResult.getString("openid");
        String unionid = tokenResult.getString("unionid");
        String accessToken = tokenResult.getString("access_token");

        JSONObject wxUserInfo = getWxUserInfo(accessToken, openid);
        if (wxUserInfo == null) {
            log.error("获取微信用户信息失败: openid={}", openid);
            return html;
        }

        SysWechatUser wechatUser = findWechatBind(openid);
        if (wechatUser != null && wechatUser.getBindStatus() == 1) {
            SysUser sysUser = sysUserMapper.selectById(wechatUser.getUserId());
            if (sysUser == null || sysUser.getIsDeleted() == 1) {
                log.error("微信绑定的本地用户不存在或已删除: userId={}", wechatUser.getUserId());
                qrData.put("status", 5);
                qrData.put("openid", openid);
                qrData.put("wxUserInfo", wxUserInfo);
                redisTemplate.opsForValue().set(qrKey, qrData.toJSONString(),
                        wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);
                return html;
            }

            String token = UUID.randomUUID().toString().replace("-", "");
            redisTemplate.opsForValue().set(USER_LOGIN_REDIS_PREFIX + token,
                    JSONObject.toJSONString(sysUser), 365, TimeUnit.DAYS);

            qrData.put("status", 2);
            qrData.put("token", token);
            qrData.put("userId", sysUser.getId());
            redisTemplate.opsForValue().set(qrKey, qrData.toJSONString(),
                    wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);

            updateWechatLoginInfo(wechatUser.getId(), wxUserInfo);
            saveLoginLogAsync(sysUser.getId(), sysUser.getUsername(), 2, 1, openid, null, null);
            updateTicketStatusAsync(ticket, 2, sysUser.getId(), openid);
        } else {
            qrData.put("status", 5);
            qrData.put("openid", openid);
            qrData.put("unionid", unionid);
            qrData.put("wxUserInfo", wxUserInfo);
            redisTemplate.opsForValue().set(qrKey, qrData.toJSONString(),
                    wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);
            updateTicketStatusAsync(ticket, 5, null, openid);
            saveLoginLogAsync(null, wxUserInfo.getString("nickname"), 2, 0, openid, "本地账号未绑定", null);
        }

        return html;
    }

    @Override
    public WxLoginStatusVo bindAccount(WxLoginBindDto dto, String clientIp) {
        String qrKey = QR_REDIS_PREFIX + dto.getTicket();
        String qrJson = redisTemplate.opsForValue().get(qrKey);

        WxLoginStatusVo vo = new WxLoginStatusVo();
        vo.setTicket(dto.getTicket());

        if (StringUtils.isBlank(qrJson)) {
            vo.setStatus(3);
            vo.setMessage("二维码已过期，请刷新");
            return vo;
        }

        JSONObject qrData = JSON.parseObject(qrJson);
        Integer status = qrData.getInteger("status");
        if (status == null || status != 5) {
            vo.setStatus(status == null ? 3 : status);
            vo.setMessage("当前状态不允许绑定");
            return vo;
        }

        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getUsername, dto.getUserName())
                .eq(SysUser::getIsDeleted, 0)
                .last("limit 1");
        SysUser sysUser = sysUserMapper.selectOne(wrapper);
        if (Objects.isNull(sysUser)) {
            throw new ServiceException(ResultCodeEnum.LOGIN_ERROR);
        }

        String md5Password = DigestUtils.md5DigestAsHex(dto.getPassword().getBytes());
        if (!StringUtils.equals(sysUser.getPassword(), md5Password)) {
            throw new ServiceException(ResultCodeEnum.LOGIN_ERROR);
        }

        String openid = qrData.getString("openid");
        String unionid = qrData.getString("unionid");
        JSONObject wxUserInfo = qrData.getJSONObject("wxUserInfo");

        SysWechatUser existingBind = findWechatBind(openid);
        if (existingBind != null) {
            existingBind.setUserId(sysUser.getId());
            existingBind.setBindStatus(1);
            existingBind.setUpdateTime(LocalDateTime.now());
            sysWechatUserMapper.updateById(existingBind);
        } else {
            SysWechatUser newBind = new SysWechatUser();
            newBind.setUserId(sysUser.getId());
            newBind.setOpenid(openid);
            newBind.setUnionid(unionid);
            newBind.setAppid(wxLoginProperties.getAppId());
            if (wxUserInfo != null) {
                newBind.setNickname(wxUserInfo.getString("nickname"));
                newBind.setAvatarUrl(wxUserInfo.getString("headimgurl"));
                newBind.setSex(wxUserInfo.getInteger("sex"));
                newBind.setCountry(wxUserInfo.getString("country"));
                newBind.setProvince(wxUserInfo.getString("province"));
                newBind.setCity(wxUserInfo.getString("city"));
            }
            newBind.setBindStatus(1);
            newBind.setLastLoginTime(LocalDateTime.now());
            newBind.setLastLoginIp(clientIp);
            newBind.setCreateTime(LocalDateTime.now());
            newBind.setIsDeleted(0);
            sysWechatUserMapper.insert(newBind);
        }

        String token = UUID.randomUUID().toString().replace("-", "");
        redisTemplate.opsForValue().set(USER_LOGIN_REDIS_PREFIX + token,
                JSONObject.toJSONString(sysUser), 365, TimeUnit.DAYS);

        qrData.put("status", 2);
        qrData.put("token", token);
        qrData.put("userId", sysUser.getId());
        redisTemplate.opsForValue().set(qrKey, qrData.toJSONString(),
                wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);

        vo.setStatus(2);
        vo.setMessage("绑定并登录成功");
        vo.setToken(token);

        updateTicketStatusAsync(dto.getTicket(), 2, sysUser.getId(), openid);
        saveLoginLogAsync(sysUser.getId(), sysUser.getUsername(), 2, 1, openid, null, clientIp);
        return vo;
    }

    @Override
    public void unbind() {
        SysUser currentUser = AuthContextUtil.getUser();
        if (currentUser == null) {
            throw new ServiceException(ResultCodeEnum.LOGIN_AUTH);
        }

        LambdaUpdateWrapper<SysWechatUser> wrapper = new LambdaUpdateWrapper<SysWechatUser>()
                .eq(SysWechatUser::getUserId, currentUser.getId())
                .eq(SysWechatUser::getBindStatus, 1)
                .eq(SysWechatUser::getIsDeleted, 0)
                .set(SysWechatUser::getBindStatus, 0)
                .set(SysWechatUser::getUpdateTime, LocalDateTime.now());
        sysWechatUserMapper.update(null, wrapper);
    }

    @Override
    public WxLoginBindInfoVo getBindInfo() {
        SysUser currentUser = AuthContextUtil.getUser();
        WxLoginBindInfoVo vo = new WxLoginBindInfoVo();
        vo.setBinded(false);

        if (currentUser == null) {
            return vo;
        }

        LambdaQueryWrapper<SysWechatUser> wrapper = new LambdaQueryWrapper<SysWechatUser>()
                .eq(SysWechatUser::getUserId, currentUser.getId())
                .eq(SysWechatUser::getBindStatus, 1)
                .eq(SysWechatUser::getIsDeleted, 0)
                .last("limit 1");
        SysWechatUser wechatUser = sysWechatUserMapper.selectOne(wrapper);

        if (wechatUser != null) {
            vo.setBinded(true);
            vo.setNickname(wechatUser.getNickname());
            vo.setAvatarUrl(wechatUser.getAvatarUrl());
            vo.setBindTime(wechatUser.getCreateTime() != null
                    ? wechatUser.getCreateTime().toString() : null);
        }
        return vo;
    }

    @Override
    public void cleanExpiredTickets() {
        LambdaUpdateWrapper<SysQrLoginTicket> wrapper = new LambdaUpdateWrapper<SysQrLoginTicket>()
                .eq(SysQrLoginTicket::getStatus, 0)
                .lt(SysQrLoginTicket::getExpireTime, LocalDateTime.now())
                .set(SysQrLoginTicket::getStatus, 3);
        sysQrLoginTicketMapper.update(null, wrapper);
    }

    @Override
    public void mockScan(String ticket) {
        String key = QR_REDIS_PREFIX + ticket;
        String qrJson = redisTemplate.opsForValue().get(key);
        if (StringUtils.isBlank(qrJson)) {
            return;
        }
        JSONObject qrData = JSON.parseObject(qrJson);
        Integer status = qrData.getInteger("status");
        if (status != null && status == 0) {
            qrData.put("status", 1);
            redisTemplate.opsForValue().set(key, qrData.toJSONString(),
                    wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);
            updateTicketStatusAsync(ticket, 1, null, null);
        }
    }

    @Override
    public void mockConfirm(String ticket) {
        String key = QR_REDIS_PREFIX + ticket;
        String qrJson = redisTemplate.opsForValue().get(key);
        if (StringUtils.isBlank(qrJson)) {
            log.warn("Mock确认: 票据不存在或已过期: ticket={}", ticket);
            return;
        }
        JSONObject qrData = JSON.parseObject(qrJson);
        Integer status = qrData.getInteger("status");
        if (status != null && status >= 2) {
            return;
        }

        String mockOpenid = "mock_openid_" + ticket.substring(0, 8);
        qrData.put("status", 1);
        redisTemplate.opsForValue().set(key, qrData.toJSONString(),
                wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);

        SysWechatUser wechatUser = findWechatBind(mockOpenid);
        if (wechatUser != null && wechatUser.getBindStatus() == 1) {
            SysUser sysUser = sysUserMapper.selectById(wechatUser.getUserId());
            if (sysUser != null && sysUser.getIsDeleted() == 0) {
                String token = UUID.randomUUID().toString().replace("-", "");
                redisTemplate.opsForValue().set(USER_LOGIN_REDIS_PREFIX + token,
                        JSONObject.toJSONString(sysUser), 365, TimeUnit.DAYS);
                qrData.put("status", 2);
                qrData.put("token", token);
                qrData.put("userId", sysUser.getId());
                redisTemplate.opsForValue().set(key, qrData.toJSONString(),
                        wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);
                updateWechatLoginInfo(wechatUser.getId(), null);
                saveLoginLogAsync(sysUser.getId(), sysUser.getUsername(), 2, 1, mockOpenid, null, null);
                updateTicketStatusAsync(ticket, 2, sysUser.getId(), mockOpenid);
                return;
            }
        }

        JSONObject mockWxUserInfo = new JSONObject();
        mockWxUserInfo.put("nickname", "微信用户(Mock)");
        mockWxUserInfo.put("headimgurl", "");
        mockWxUserInfo.put("sex", 0);
        qrData.put("status", 5);
        qrData.put("openid", mockOpenid);
        qrData.put("unionid", null);
        qrData.put("wxUserInfo", mockWxUserInfo);
        redisTemplate.opsForValue().set(key, qrData.toJSONString(),
                wxLoginProperties.getQrTtlSeconds(), TimeUnit.SECONDS);
        updateTicketStatusAsync(ticket, 5, null, mockOpenid);
        saveLoginLogAsync(null, "微信用户(Mock)", 2, 0, mockOpenid, "本地账号未绑定", null);
    }

    private String findTicketByState(String state) {
        LambdaQueryWrapper<SysQrLoginTicket> wrapper = new LambdaQueryWrapper<SysQrLoginTicket>()
                .eq(SysQrLoginTicket::getState, state)
                .last("limit 1");
        SysQrLoginTicket ticket = sysQrLoginTicketMapper.selectOne(wrapper);
        return ticket != null ? ticket.getTicket() : null;
    }

    private SysWechatUser findWechatBind(String openid) {
        LambdaQueryWrapper<SysWechatUser> wrapper = new LambdaQueryWrapper<SysWechatUser>()
                .eq(SysWechatUser::getAppid, wxLoginProperties.getAppId())
                .eq(SysWechatUser::getOpenid, openid)
                .eq(SysWechatUser::getIsDeleted, 0)
                .last("limit 1");
        return sysWechatUserMapper.selectOne(wrapper);
    }

    private JSONObject getWxAccessToken(String code) {
        String url = wxLoginProperties.getAccessTokenUrl()
                + "?appid=" + wxLoginProperties.getAppId()
                + "&secret=" + wxLoginProperties.getAppSecret()
                + "&code=" + code
                + "&grant_type=authorization_code";
        try {
            String result = HttpUtil.get(url, 5000);
            JSONObject json = JSON.parseObject(result);
            if (json.containsKey("errcode") && json.getInteger("errcode") != 0) {
                log.error("微信获取access_token错误: {}", result);
                return null;
            }
            return json;
        } catch (Exception e) {
            log.error("请求微信access_token异常", e);
            return null;
        }
    }

    private JSONObject getWxUserInfo(String accessToken, String openid) {
        String url = wxLoginProperties.getUserInfoUrl()
                + "?access_token=" + accessToken
                + "&openid=" + openid
                + "&lang=zh_CN";
        try {
            String result = HttpUtil.get(url, 5000);
            JSONObject json = JSON.parseObject(result);
            if (json.containsKey("errcode") && json.getInteger("errcode") != 0) {
                log.error("微信获取用户信息错误: {}", result);
                return null;
            }
            return json;
        } catch (Exception e) {
            log.error("请求微信用户信息异常", e);
            return null;
        }
    }

    private void updateWechatLoginInfo(Long id, JSONObject wxUserInfo) {
        LambdaUpdateWrapper<SysWechatUser> wrapper = new LambdaUpdateWrapper<SysWechatUser>()
                .eq(SysWechatUser::getId, id)
                .set(SysWechatUser::getLastLoginTime, LocalDateTime.now());
        if (wxUserInfo != null) {
            wrapper.set(SysWechatUser::getNickname, wxUserInfo.getString("nickname"));
            wrapper.set(SysWechatUser::getAvatarUrl, wxUserInfo.getString("headimgurl"));
        }
        sysWechatUserMapper.update(null, wrapper);
    }

    @Async
    public void saveTicketAsync(String ticket, String state, String clientIp) {
        try {
            SysQrLoginTicket entity = new SysQrLoginTicket();
            entity.setTicket(ticket);
            entity.setState(state);
            entity.setStatus(0);
            entity.setClientIp(clientIp);
            entity.setExpireTime(LocalDateTime.now().plusSeconds(wxLoginProperties.getQrTtlSeconds()));
            entity.setCreateTime(LocalDateTime.now());
            entity.setUpdateTime(LocalDateTime.now());
            sysQrLoginTicketMapper.insert(entity);
        } catch (Exception e) {
            log.error("异步保存票据失败: ticket={}", ticket, e);
        }
    }

    @Async
    public void updateTicketStatusAsync(String ticket, Integer status, Long userId, String openid) {
        try {
            LambdaUpdateWrapper<SysQrLoginTicket> wrapper = new LambdaUpdateWrapper<SysQrLoginTicket>()
                    .eq(SysQrLoginTicket::getTicket, ticket)
                    .set(SysQrLoginTicket::getStatus, status)
                    .set(SysQrLoginTicket::getUpdateTime, LocalDateTime.now());
            if (userId != null) {
                wrapper.set(SysQrLoginTicket::getUserId, userId);
            }
            if (openid != null) {
                wrapper.set(SysQrLoginTicket::getOpenid, openid);
            }
            sysQrLoginTicketMapper.update(null, wrapper);
        } catch (Exception e) {
            log.error("异步更新票据状态失败: ticket={}", ticket, e);
        }
    }

    @Async
    public void saveLoginLogAsync(Long userId, String username, Integer loginType,
                                  Integer loginStatus, String openid,
                                  String failReason, String clientIp) {
        try {
            SysLoginLog logEntity = new SysLoginLog();
            logEntity.setUserId(userId);
            logEntity.setUsername(username);
            logEntity.setLoginType(loginType);
            logEntity.setLoginStatus(loginStatus);
            logEntity.setOpenid(openid);
            logEntity.setFailReason(failReason);
            logEntity.setIpAddress(clientIp);
            logEntity.setCreateTime(LocalDateTime.now());
            sysLoginLogMapper.insert(logEntity);
        } catch (Exception e) {
            log.error("异步保存登录日志失败", e);
        }
    }
}
