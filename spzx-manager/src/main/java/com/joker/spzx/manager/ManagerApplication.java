package com.joker.spzx.manager;

import com.joker.spzx.common.annotation.EnableLogAspect;
import com.joker.spzx.common.exception.GlobalExceptionHandler;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
import org.springframework.scheduling.annotation.EnableAsync;

// proxyTargetClass=true：@EnableAsync 默认走 JDK 接口代理，会把带 @Async 的 service 暴露成
// $Proxy 对象，而 WxLoginServiceImpl 按具体类型自注入代理（self.xxxAsync），首次调用即
// BeanNotOfRequiredTypeException（dev 登录 500）。与 Boot 自身的 CGLIB 默认保持一致。
@EnableAsync(proxyTargetClass = true)
@EnableLogAspect
@SpringBootApplication
@Import(GlobalExceptionHandler.class)
public class ManagerApplication {

    public static void main(String[] args) {
        SpringApplication.run(ManagerApplication.class, args);
    }
}
