package com.joker.spzx.manager.service.impl;

import cn.hutool.captcha.CaptchaUtil;
import cn.hutool.captcha.CircleCaptcha;
import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.joker.spzx.common.exception.ServiceException;
import com.joker.spzx.manager.mapper.SysUserMapper;
import com.joker.spzx.manager.mapper.SysUserRoleMapper;
import com.joker.spzx.manager.service.SysUserService;
import com.joker.spzx.model.dto.system.AssginRoleDto;
import com.joker.spzx.model.dto.system.LoginDto;
import com.joker.spzx.model.dto.system.SysUserDto;
import com.joker.spzx.model.entity.system.SysRoleUser;
import com.joker.spzx.model.entity.system.SysUser;
import com.joker.spzx.model.vo.common.ResultCodeEnum;
import com.joker.spzx.model.vo.system.LoginVo;
import com.joker.spzx.model.vo.system.ValidateCodeVo;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.DigestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * <p>
 * 用户表 服务实现类
 * </p>
 *
 * @author joker
 * @since 2025-04-15 17:07:15
 */
@Service
public class SysUserServiceImpl extends ServiceImpl<SysUserMapper, SysUser> implements SysUserService {


    @Autowired
    private RedisTemplate<String, String> redisTemplate;

    @Autowired
    private SysUserRoleMapper sysUserRoleMapper;

    @Override
    public LoginVo login(LoginDto loginDto) {

        //校验验证码是否正确
        String codeKey = loginDto.getCodeKey();
        String s1 = redisTemplate.opsForValue().get("user:login:validatecode:" + codeKey);
        if (!StringUtils.equalsIgnoreCase(loginDto.getCaptcha(), s1)) {
            throw new ServiceException(ResultCodeEnum.VALIDATECODE_ERROR);
        }
        // 验证通过删除redis中的验证码

        redisTemplate.delete("user:login:validatecode:" + codeKey);

        LambdaQueryWrapper<SysUser> eq = lambdaQuery().getWrapper().eq(SysUser::getUsername, loginDto.getUserName())
                .eq(SysUser::getIsDeleted, 0)
                .last(" limit 1");
        SysUser one = this.getOne(eq);
        if (Objects.isNull(one)) {
            throw new ServiceException(ResultCodeEnum.LOGIN_ERROR);
        }
        String md5InputPassword = DigestUtils.md5DigestAsHex(loginDto.getPassword().getBytes());
        if (!StringUtils.equals(one.getPassword(), md5InputPassword)) {
            throw new ServiceException(ResultCodeEnum.LOGIN_ERROR);
        }
        String replace = UUID.randomUUID().toString().replace("-", "");
        redisTemplate.opsForValue().set("user:login:" + replace, JSONObject.toJSONString(one), 7, TimeUnit.DAYS);
        LoginVo loginVo = new LoginVo();
        loginVo.setToken(replace);
        return loginVo;

    }

    @Override
    public ValidateCodeVo genVarifyCode() {
        CircleCaptcha circleCaptcha = CaptchaUtil.createCircleCaptcha(150, 48, 4, 2);
        String code = circleCaptcha.getCode();
        String imageBase64 = circleCaptcha.getImageBase64();

        String key = UUID.randomUUID().toString().replace("-", "");
        // 将验证码存储到Redis中
        redisTemplate.opsForValue().set("user:login:validatecode:" + key, code, 5, TimeUnit.MINUTES);
        ValidateCodeVo validateCodeVo = new ValidateCodeVo();
        validateCodeVo.setCodeKey(key);
        validateCodeVo.setCodeValue("data:image/png;base64," + imageBase64);
        return validateCodeVo;
    }

    @Override
    public SysUser getUserInfo(String token) {
        String userJson = redisTemplate.opsForValue().get("user:login:" + token);
        return JSON.parseObject(userJson, SysUser.class);
    }

    @Override
    public void logout(String token) {
        redisTemplate.delete("user:login:" + token);
    }

    @Override
    public IPage<SysUser> findByPage(SysUserDto sysUserDto, Integer pageNum, Integer pageSize) {
        IPage<SysUser> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<SysUser> eq = lambdaQuery().getWrapper()
                .like(StringUtils.isNotBlank(sysUserDto.getKeyword()), SysUser::getName, sysUserDto.getKeyword())
                .eq(SysUser::getIsDeleted, 0);
        return this.page(page, eq);
    }

    @Override
    public void saveSysUser(SysUser sysUser) {
        this.verifyUserName(sysUser.getUsername());
        String s = DigestUtils.md5DigestAsHex(sysUser.getPassword().getBytes());
        sysUser.setPassword(s);

        sysUser.setIsDeleted(0);
        sysUser.setCreateTime(LocalDateTime.now());
        this.save(sysUser);
    }

    private void verifyUserName(String username) {
        LambdaQueryWrapper<SysUser> last = lambdaQuery().getWrapper().eq(SysUser::getUsername, username)
                .eq(SysUser::getIsDeleted, 0)
                .last("limit 1");
        SysUser one = this.getOne(last);
        if (Objects.nonNull(one)) {
            throw new ServiceException(ResultCodeEnum.USERNAME_EXISTS);
        }
    }

    @Override
    public void updateSysUser(SysUser sysUser) {
        sysUser.setUpdateTime(LocalDateTime.now());
        this.updateById(sysUser);
    }

    @Override
    public void deleteSysUser(Long id) {
        SysUser sysUser = new SysUser();
        sysUser.setId(id);
        sysUser.setIsDeleted(1);
        sysUser.setUpdateTime(LocalDateTime.now());
        this.updateById(sysUser);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void assignRole(AssginRoleDto assginRoleDto) {
        Long userId = assginRoleDto.getUserId();
        LambdaQueryWrapper<SysRoleUser> eq = new LambdaQueryWrapper<SysRoleUser>().eq(SysRoleUser::getUserId, userId);
        sysUserRoleMapper.delete(eq);
        List<SysRoleUser> collect = assginRoleDto.getRoleIdList().stream().map(roleId -> new SysRoleUser() {{
            setRoleId(roleId);
            setUserId(userId);
        }}).collect(Collectors.toList());

        sysUserRoleMapper.insert(collect);

    }

}
