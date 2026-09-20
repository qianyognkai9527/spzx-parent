package com.joker.spzx.common.util;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 子进程执行工具: 统一超时、输出消费与进程/流清理, 避免「读到 EOF 才 waitFor」导致的线程挂死与 fd 泄漏
 */
public final class ShellUtil {

    private ShellUtil() {
    }

    public static ShellResult run(String cmd, long timeoutMs) {
        return execute(new ProcessBuilder("sh", "-c", cmd), timeoutMs);
    }

    public static ShellResult run(List<String> cmd, long timeoutMs) {
        return execute(new ProcessBuilder(cmd), timeoutMs);
    }

    private static ShellResult execute(ProcessBuilder pb, long timeoutMs) {
        pb.redirectErrorStream(true);
        Process p = null;
        StringBuilder out = new StringBuilder();
        boolean timedOut = false;
        boolean interrupted = false;
        try {
            p = pb.start();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                char[] buf = new char[8192];
                long deadline = System.currentTimeMillis() + Math.max(1L, timeoutMs);
                while (!p.waitFor(50, TimeUnit.MILLISECONDS)) {
                    drain(reader, buf, out);
                    if (System.currentTimeMillis() >= deadline) {
                        timedOut = true;
                        break;
                    }
                }
                if (timedOut) {
                    p.destroyForcibly();
                    boolean dead = false;
                    try {
                        dead = p.waitFor(5, TimeUnit.SECONDS);
                    } catch (InterruptedException ie) {
                        interrupted = true;
                    }
                    if (dead) {
                        drainAll(reader, buf, out);
                    }
                } else {
                    drainAll(reader, buf, out);
                }
            }
        } catch (IOException e) {
            out.append("\n[ShellUtil] IO error: ").append(e.getMessage());
        } catch (InterruptedException e) {
            interrupted = true;
            out.append("\n[ShellUtil] interrupted");
        } finally {
            if (p != null) {
                p.destroy();
            }
            if (interrupted) {
                Thread.currentThread().interrupt();
            }
        }
        int exitCode = -1;
        if (p != null) {
            try {
                exitCode = p.exitValue();
            } catch (IllegalThreadStateException ignored) {
            }
        }
        return new ShellResult(exitCode, out.toString(), timedOut);
    }

    private static void drain(BufferedReader reader, char[] buf, StringBuilder out) throws IOException {
        while (reader.ready()) {
            int n = reader.read(buf);
            if (n < 0) {
                return;
            }
            out.append(buf, 0, n);
        }
    }

    private static void drainAll(BufferedReader reader, char[] buf, StringBuilder out) throws IOException {
        int n;
        while ((n = reader.read(buf)) >= 0) {
            out.append(buf, 0, n);
        }
    }

    /**
     * @param exitCode 进程退出码; 进程未能正常退出(超时强杀/IO 异常/中断)时为 -1
     */
    public record ShellResult(int exitCode, String output, boolean timedOut) {
    }
}
