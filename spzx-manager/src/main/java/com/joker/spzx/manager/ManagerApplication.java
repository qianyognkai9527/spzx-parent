package com.joker.spzx.manager;

import com.joker.spzx.common.annotation.EnableLogAspect;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@EnableAsync
@EnableLogAspect
@SpringBootApplication
public class ManagerApplication {

    public static void main(String[] args) {
        SpringApplication.run(ManagerApplication.class, args);
    }
}
