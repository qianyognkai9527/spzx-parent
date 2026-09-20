package com.joker.spzx.model.enums;

import lombok.Getter;

/**
 * 平台类型枚举（platform_type: 1=淘宝 2=抖音）
 */
@Getter
public enum PlatformTypeEnum {

    TAOBAO(1, "淘宝"),
    DOUYIN(2, "抖音"),

    ;

    private final Integer code;
    private final String name;

    PlatformTypeEnum(Integer code, String name) {
        this.code = code;
        this.name = name;
    }

    /**
     * 返回平台中文名，code 为 null 或未匹配时返回空串
     */
    public static String nameOf(Integer code) {
        for (PlatformTypeEnum e : values()) {
            if (e.code.equals(code)) {
                return e.name;
            }
        }
        return "";
    }

    /**
     * 返回平台中文名，code 为 null 或未匹配时返回 defaultName
     */
    public static String nameOfOrDefault(Integer code, String defaultName) {
        for (PlatformTypeEnum e : values()) {
            if (e.code.equals(code)) {
                return e.name;
            }
        }
        return defaultName;
    }
}
