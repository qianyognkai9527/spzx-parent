package com.joker.spzx.manager.service;

import com.alibaba.fastjson.JSON;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;

@Service
public class IdempotentService {

    @Autowired
    private StringRedisTemplate redis;

    public boolean acquire(String key, Duration ttl) {
        Boolean result = redis.opsForValue().setIfAbsent(key, "1", ttl);
        return Boolean.TRUE.equals(result);
    }

    public void cacheResult(String key, Object result, Duration ttl) {
        redis.opsForValue().set(key, JSON.toJSONString(result), ttl);
    }

    public <T> T getCachedResult(String key, Class<T> clazz) {
        String json = redis.opsForValue().get(key);
        return json != null ? JSON.parseObject(json, clazz) : null;
    }

    public void release(String key) {
        redis.delete(key);
    }

    public boolean exists(String key) {
        return Boolean.TRUE.equals(redis.hasKey(key));
    }
}
