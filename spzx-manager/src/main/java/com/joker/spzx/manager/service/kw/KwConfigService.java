package com.joker.spzx.manager.service.kw;

import com.joker.spzx.manager.mapper.KwConfigMapper;
import com.joker.spzx.model.entity.kw.KwConfig;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class KwConfigService {

    public static final String KEY_TEXT = "text_provider";
    public static final String KEY_VISION = "vision_provider";
    public static final String KEY_VIDEO = "video_provider";
    public static final String KEY_VIDEO_BUDGET = "video_daily_budget";
    public static final String DEFAULT_PROVIDER = "tokens-store";

    @Autowired
    private KwConfigMapper kwConfigMapper;

    public String getProvider(String key) {
        KwConfig c = kwConfigMapper.selectById(key);
        return c == null || c.getConfigValue() == null || c.getConfigValue().isBlank()
                ? DEFAULT_PROVIDER : c.getConfigValue();
    }

    public void setProvider(String key, String value) {
        KwConfig c = new KwConfig();
        c.setConfigKey(key);
        c.setConfigValue(value);
        if (kwConfigMapper.selectById(key) == null) {
            kwConfigMapper.insert(c);
        } else {
            kwConfigMapper.updateById(c);
        }
        log.info("kw引擎切换: {} -> {}", key, value);
    }

    public String getValue(String key) {
        KwConfig c = kwConfigMapper.selectById(key);
        return c == null ? null : c.getConfigValue();
    }

    public void setValue(String key, String value) {
        KwConfig c = new KwConfig();
        c.setConfigKey(key);
        c.setConfigValue(value);
        if (kwConfigMapper.selectById(key) == null) {
            kwConfigMapper.insert(c);
        } else {
            kwConfigMapper.updateById(c);
        }
    }
}
