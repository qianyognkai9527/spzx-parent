package com.joker.spzx.manager;

import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import lombok.extern.slf4j.Slf4j;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;

@Slf4j
@SpringBootTest
public class EmailTest {

    @Autowired
    private JavaMailSender javaMailSender;

    @Value("${spring.mail.username}")
    private String from;

    // 收件人邮箱（修改为实际测试目标邮箱）
    private static final String TO = "1404096574@qq.com";

    /**
     * 发送简单纯文本邮件
     */
    @Test
    public void testSendSimpleMail() {
        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(from);
        message.setTo(TO);
        message.setSubject("测试邮件");
        message.setText("这是一封测试邮件");

        javaMailSender.send(message);
        log.info("简单邮件发送成功！from={}, to={}", from, TO);
    }

    /**
     * 发送 HTML 格式邮件
     */
    @Test
    public void testSendHtmlMail() throws MessagingException {
        MimeMessage mimeMessage = javaMailSender.createMimeMessage();
        MimeMessageHelper helper = new MimeMessageHelper(mimeMessage, true, "UTF-8");

        helper.setFrom(from);
        helper.setTo(TO);
        helper.setSubject("【测试】HTML邮件");
        helper.setText("<html><body>"
                + "<h2 style='color:#4CAF50;'>邮件发送测试成功</h2>"
                + "<p>这是一封 <b>HTML</b> 格式的测试邮件。</p>"
                + "</body></html>", true);

        javaMailSender.send(mimeMessage);
        log.info("HTML邮件发送成功！from={}, to={}", from, TO);
    }
}
