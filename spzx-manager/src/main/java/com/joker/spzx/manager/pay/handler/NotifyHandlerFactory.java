package com.joker.spzx.manager.pay.handler;

import com.joker.spzx.manager.pay.handler.ChannelNotifyHandler;
import com.joker.spzx.model.exception.PayException;
import com.joker.spzx.model.enums.pay.PayErrorCode;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Component
public class NotifyHandlerFactory {

    private final Map<String, ChannelNotifyHandler> handlerMap;

    public NotifyHandlerFactory(List<ChannelNotifyHandler> handlers) {
        this.handlerMap = handlers.stream()
            .collect(Collectors.toMap(ChannelNotifyHandler::getChannel, Function.identity()));
    }

    public ChannelNotifyHandler getHandler(String channel) {
        ChannelNotifyHandler handler = handlerMap.get(channel);
        if (handler == null) {
            handler = handlerMap.get("generic");
        }
        if (handler == null) {
            throw new PayException(PayErrorCode.CHANNEL_UNAVAILABLE, channel);
        }
        return handler;
    }
}
