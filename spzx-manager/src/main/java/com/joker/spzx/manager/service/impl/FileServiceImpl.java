package com.joker.spzx.manager.service.impl;

import cn.hutool.core.date.DateUtil;
import com.joker.spzx.manager.service.FileService;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.Date;


@Slf4j
@Service
public class FileServiceImpl implements FileService {

    @Value("${minio.endpoint:http://127.0.0.1:9000}")
    private String endpoint;

    @Value("${minio.access-key:minioadmin}")
    private String accessKey;

    @Value("${minio.secret-key:minioadmin}")
    private String secretKey;

    @Value("${minio.bucket:spzx-manager}")
    private String bucket;

    private MinioClient minioClient;

    @PostConstruct
    public void init() {
        minioClient = MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
        try {
            boolean found = minioClient.bucketExists(BucketExistsArgs.builder().bucket(bucket).build());
            if (!found) {
                minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
            }
        } catch (Exception e) {
            // MinIO 未运行时降级:不阻塞启动,上传时再报错
            log.warn("MinIO 初始化失败(文件上传暂不可用): {}", e.getMessage());
        }
    }

    @Override
    public String fileUpload(MultipartFile file) {
        try {
            String dateDir = DateUtil.format(new Date(), "yyyyMMdd");
            String fileName = dateDir + "/" + file.getOriginalFilename();

            PutObjectArgs putObjectArgs = PutObjectArgs.builder()
                    .bucket(bucket)
                    .stream(file.getInputStream(), file.getSize(), -1)
                    .object(fileName)
                    .build();
            minioClient.putObject(putObjectArgs);

            return endpoint + "/" + bucket + "/" + fileName;

        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
