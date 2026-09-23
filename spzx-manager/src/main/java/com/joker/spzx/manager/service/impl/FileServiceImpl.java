package com.joker.spzx.manager.service.impl;

import cn.hutool.core.date.DateUtil;
import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.StrUtil;
import com.joker.spzx.manager.service.FileService;
import io.minio.BucketExistsArgs;
import io.minio.GetObjectArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Date;
import java.util.UUID;


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
            // 对象键用 UUID, 不信任原始文件名(防目录穿越/同名覆盖)
            String ext = FileUtil.extName(file.getOriginalFilename());
            String objectName = dateDir + "/" + UUID.randomUUID().toString().replace("-", "")
                    + (StrUtil.isBlank(ext) ? "" : "." + ext);

            PutObjectArgs putObjectArgs = PutObjectArgs.builder()
                    .bucket(bucket)
                    .stream(file.getInputStream(), file.getSize(), -1)
                    .object(objectName)
                    .build();
            minioClient.putObject(putObjectArgs);

            return endpoint + "/" + bucket + "/" + objectName;

        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public byte[] readBytes(String fileUrl) {
        try {
            String prefix = endpoint + "/" + bucket + "/";
            if (fileUrl != null && fileUrl.startsWith(prefix)) {
                // 本 bucket 对象: 走 MinIO 客户端读回
                String object = fileUrl.substring(prefix.length());
                try (InputStream in = minioClient.getObject(
                        GetObjectArgs.builder().bucket(bucket).object(object).build())) {
                    return in.readAllBytes();
                }
            }
            // 跨 bucket / 外部 URL(如 Ark 返回的公网 video_url): 直接 HTTP GET
            HttpURLConnection conn = (HttpURLConnection) new URL(fileUrl).openConnection();
            conn.setConnectTimeout(10_000);
            conn.setReadTimeout(30_000);
            conn.setInstanceFollowRedirects(true); // 跟随同协议 302 跳转
            try (InputStream in = conn.getInputStream()) {
                return in.readAllBytes();
            }
        } catch (Exception e) {
            // 非 2xx 响应 getInputStream() 抛 IOException, 统一包装为 RuntimeException
            throw new RuntimeException("读取文件失败: " + e.getMessage(), e);
        }
    }

    @Override
    public String uploadBytes(String objectKey, byte[] data, String contentType) {
        try (InputStream in = new ByteArrayInputStream(data)) {
            minioClient.putObject(PutObjectArgs.builder()
                    .bucket(bucket)
                    .object(objectKey)
                    .stream(in, data.length, -1)
                    .contentType(contentType)
                    .build());
            return endpoint + "/" + bucket + "/" + objectKey;
        } catch (Exception e) {
            throw new RuntimeException("上传失败: " + e.getMessage(), e);
        }
    }

    @Override
    public String presignedDownloadUrl(String objectKey, String filename) {
        try {
            // minio 8.5.2 无 extraHttpHeaders；S3 规范下 response-* 覆盖须走查询参数
            return minioClient.getPresignedObjectUrl(io.minio.GetPresignedObjectUrlArgs.builder()
                    .method(io.minio.http.Method.GET)
                    .bucket(bucket)
                    .object(objectKey)
                    .expiry(1, java.util.concurrent.TimeUnit.HOURS)
                    .extraQueryParams(java.util.Map.of(
                            "response-content-disposition",
                            "attachment; filename=\"" + filename.replace("\"", "") + "\""))
                    .build());
        } catch (Exception e) {
            throw new RuntimeException("生成下载链接失败: " + e.getMessage(), e);
        }
    }
}
