package com.joker.spzx.manager.service;

import org.springframework.web.multipart.MultipartFile;

public interface FileService {
    String fileUpload(MultipartFile file);

    /** 按 URL 读回文件字节：本 bucket 走 MinIO，跨 bucket/外部 URL 直接 HTTP GET */
    byte[] readBytes(String fileUrl);

    /** 字节上传到本 bucket，返回可访问 URL */
    String uploadBytes(String objectKey, byte[] data, String contentType);
}
