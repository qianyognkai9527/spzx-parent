package com.joker.spzx.manager.config;


import com.baomidou.mybatisplus.annotation.DbType;
import com.baomidou.mybatisplus.core.incrementer.DefaultIdentifierGenerator;
import com.baomidou.mybatisplus.core.incrementer.IdentifierGenerator;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.OptimisticLockerInnerInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.PaginationInnerInterceptor;
import com.baomidou.mybatisplus.extension.plugins.pagination.dialects.MySqlDialect;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Slf4j
@Configuration(proxyBeanMethods = false)
public class MybatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        // 乐观锁
        interceptor.addInnerInterceptor(new OptimisticLockerInnerInterceptor());
        PaginationInnerInterceptor paginationInnerInterceptor = new PaginationInnerInterceptor();
        paginationInnerInterceptor.setDialect(new MySqlDialect());
        paginationInnerInterceptor.setDbType(DbType.MYSQL);
        paginationInnerInterceptor.setMaxLimit(500L);
        paginationInnerInterceptor.setOptimizeJoin(true);
        interceptor.addInnerInterceptor(paginationInnerInterceptor); // 分页插件
        return interceptor;
    }

    /**
     * 固定 workerId/datacenterId，绕开 MP 默认按 InetAddress 取主机信息的 5s 网络超时。
     * 本机 hostname 不在 /etc/hosts，IdentifierGeneratorAutoConfiguration 每次启动经
     * InetUtils.findFirstNonLoopbackAddress 卡 5.04s（2026-10-23 启动实测）。单机部署无冲突。
     */
    @Bean
    public IdentifierGenerator identifierGenerator() {
        return new DefaultIdentifierGenerator(1L, 1L);
    }
}
