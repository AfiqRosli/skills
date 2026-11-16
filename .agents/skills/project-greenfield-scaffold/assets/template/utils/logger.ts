/**
 * Structured logger — one call site for all console output so log
 * shape stays consistent and a real transport (Sentry breadcrumbs,
 * Better Stack) can be added later without touching call sites.
 *
 * Never log secrets, tokens, or request bodies containing credentials.
 */

type LogLevel = "debug" | "info" | "warn" | "error";

interface LogContext {
  [key: string]: unknown;
}

const shouldLog = (level: LogLevel): boolean => {
  if (level === "debug") {
    return process.env.NODE_ENV === "development";
  }
  return true;
};

const emit = (level: LogLevel, message: string, context?: LogContext) => {
  if (!shouldLog(level)) return;
  const payload = { level, message, ...context, ts: new Date().toISOString() };
  console[level === "debug" ? "log" : level](payload);
};

export const logger = {
  debug: (message: string, context?: LogContext) => emit("debug", message, context),
  info: (message: string, context?: LogContext) => emit("info", message, context),
  warn: (message: string, context?: LogContext) => emit("warn", message, context),
  error: (message: string, context?: LogContext) => emit("error", message, context),
};
