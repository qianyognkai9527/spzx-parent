package com.joker.spzx.manager.service;

import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

@Service
public class DistributedLockService {

    @Autowired
    private RedissonClient redisson;

    public <T> T executeWithLock(String lockKey, Duration waitTime, Duration leaseTime, Supplier<T> action) {
        RLock lock = redisson.getLock(lockKey);
        boolean acquired = false;
        try {
            acquired = lock.tryLock(waitTime.toMillis(), leaseTime.toMillis(), TimeUnit.MILLISECONDS);
            if (!acquired) {
                throw new PayException(PayErrorCode.ORDER_PROCESSING, lockKey);
            }
            return action.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new PayException(PayErrorCode.SYSTEM_ERROR, "获取锁被中断: " + lockKey);
        } finally {
            if (acquired && lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }

    public void executeWithLock(String lockKey, Duration waitTime, Duration leaseTime, Runnable action) {
        executeWithLock(lockKey, waitTime, leaseTime, () -> {
            action.run();
            return null;
        });
    }
}
