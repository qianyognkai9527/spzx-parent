package com.joker.spzx.manager.pay.config;

import com.paypal.base.rest.APIContext;
import com.paypal.core.PayPalEnvironment;
import com.paypal.core.PayPalHttpClient;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "pay.paypal")
public class PaypalConfig {
    private String clientId;
    private String clientSecret;
    private boolean sandbox;
    private String notifyUrl;

    @Bean
    public APIContext paypalApiContext() {
        String mode = sandbox ? "sandbox" : "live";
        return new APIContext(clientId, clientSecret, mode);
    }

    @Bean
    public PayPalHttpClient payPalHttpClient() {
        PayPalEnvironment environment = sandbox
                ? new PayPalEnvironment.Sandbox(clientId, clientSecret)
                : new PayPalEnvironment.Live(clientId, clientSecret);
        return new PayPalHttpClient(environment);
    }
}
