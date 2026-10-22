package com.joker.spzx.manager.config;

import org.mybatis.spring.mapper.MapperFactoryBean;
import org.springframework.core.NativeDetector;
import org.springframework.beans.BeansException;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.beans.factory.config.ConfigurableListableBeanFactory;
import org.springframework.beans.factory.config.ConstructorArgumentValues;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * GraalVM native 兼容补丁（2026-10-22 试验引入，JVM 行为不受影响）。
 *
 * mybatis-spring 的 ClassPathMapperScanner 给 MapperFactoryBean 的 bean 定义塞的是
 * 字符串类名构造参数（addGenericArgumentValue(beanClassName)），JVM 经典路径在
 * ConstructorResolver 里有 String→Class 类型转换；Spring AOT 的 RegisteredBean
 * 参数解析不做这个转换，直接回落 autowire 找 java.lang.Class 类型的 bean，启动即
 * "No qualifying bean of type 'java.lang.Class<?>'"（native 实测）。
 *
 * 这里在 bean 实例化前把 String 构造参数替换成同一定义里现成的 mapperInterface
 * Class 属性值，AOT 生成的 new MapperFactoryBean<>(args.get(0)) 就能拿到真 Class。
 */
@Configuration(proxyBeanMethods = false)
public class NativeCompatConfig {

    @Bean
    static BeanFactoryPostProcessor mapperConstructorArgFixer() {
        return (BeanFactoryPostProcessor) (ConfigurableListableBeanFactory beanFactory) -> {
            for (String name : beanFactory.getBeanDefinitionNames()) {
                BeanDefinition bd = beanFactory.getBeanDefinition(name);
                if (!(bd.getBeanClassName() != null && MapperFactoryBean.class.getName().equals(bd.getBeanClassName()))) {
                    continue;
                }
                Object mapperInterface = bd.getPropertyValues().get("mapperInterface");
                if (!(mapperInterface instanceof Class<?> clazz)) {
                    continue;
                }
                ConstructorArgumentValues cav = bd.getConstructorArgumentValues();
                boolean hasStringArg = cav.getGenericArgumentValues().stream()
                        .anyMatch(vh -> vh.getValue() instanceof String);
                if (hasStringArg) {
                    cav.clear();
                    cav.addGenericArgumentValue(clazz);
                }
                // AOT 生成的定义 targetType 是裸 MapperFactoryBean，by-type 注入
                // （@Autowired XxxMapper）解析不到，补成带泛型的
                if (bd instanceof org.springframework.beans.factory.support.RootBeanDefinition rbd) {
                    rbd.setTargetType(org.springframework.core.ResolvableType.forClassWithGenerics(
                            MapperFactoryBean.class, clazz));
                }
            }
        };
    }

    /**
     * springdoc 的 SwaggerWebMvcConfigurer 无条件注册 /webjars/** 资源链，Spring MVC
     * 会自动补一个 WebJarsResourceResolver，其构造器里的 WebJarAssetLocator 走 ClassGraph
     * 扫描 classpath jar——native 下必炸（ClassGraphException），连累 Tomcat 起不来。
     * JVM 上 doc.html 照常用，所以只移除 native 运行时的这个 configurer
     * （2026-10-22 GraalVM 试验实测；native 下 doc.html 本就不在验收范围）。
     */
    @Bean
    static BeanFactoryPostProcessor springdocWebUiRemover() {
        return beanFactory -> {
            if (NativeDetector.inNativeImage() && beanFactory.containsBeanDefinition("swaggerWebMvcConfigurer")) {
                ((org.springframework.beans.factory.support.BeanDefinitionRegistry) beanFactory).removeBeanDefinition("swaggerWebMvcConfigurer");
            }
        };
    }
}
