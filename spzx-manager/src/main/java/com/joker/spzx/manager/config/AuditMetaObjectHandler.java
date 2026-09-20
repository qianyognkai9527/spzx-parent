package com.joker.spzx.manager.config;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.joker.spzx.model.entity.system.SysUser;
import com.joker.spzx.utils.AuthContextUtil;
import org.apache.ibatis.reflection.MetaObject;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * BaseEntity 审计字段自动填充：insert 填 createTime/createBy，update 填 updateTime/updateBy。
 * 严格填充（strict fill）：字段已有值（如手工 set）时不覆盖；createBy/updateBy 仅在实体字段
 * 声明 fill 注解后生效（当前仅 BaseEntity 时间字段启用），无登录态时用户字段跳过填充。
 */
@Component
public class AuditMetaObjectHandler implements MetaObjectHandler {

    @Override
    public void insertFill(MetaObject metaObject) {
        strictInsertFill(metaObject, "createTime", LocalDateTime.class, LocalDateTime.now());
        strictInsertFill(metaObject, "createBy", Long.class, currentUserId());
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        strictUpdateFill(metaObject, "updateTime", LocalDateTime.class, LocalDateTime.now());
        strictUpdateFill(metaObject, "updateBy", Long.class, currentUserId());
    }

    private Long currentUserId() {
        SysUser user = AuthContextUtil.getUser();
        return user != null ? user.getId() : null;
    }
}
