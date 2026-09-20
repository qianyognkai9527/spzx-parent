package com.joker.spzx.utils.excel;

import com.alibaba.excel.EasyExcel;
import lombok.AccessLevel;
import lombok.NoArgsConstructor;

import java.io.InputStream;

/**
 * Excel相关处理
 *
 * @author 鲁子狄
 */
@NoArgsConstructor(access = AccessLevel.PRIVATE)
public class ExcelUtil {

    /**
     * 使用自定义监听器 异步导入 自定义返回
     *
     * @param is       输入流
     * @param clazz    对象类型
     * @param listener 自定义监听器
     * @return 转换后集合
     */
    public static <T> ExcelResult<T> importExcel(InputStream is, Class<T> clazz, ExcelListener<T> listener) {
        EasyExcel.read(is, clazz, listener).sheet().doRead();
        return listener.getExcelResult();
    }
}
