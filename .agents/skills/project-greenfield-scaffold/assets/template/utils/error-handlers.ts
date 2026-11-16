/**
 * Error-message helpers — extract a user-safe string from whatever an
 * API/auth boundary threw. Callers show the result in NotificationStore;
 * raw error objects never reach the UI.
 */

export function extractErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "An unexpected error occurred";
}

interface ApiErrorShape {
  error?: { message?: string };
  message?: string;
}

/**
 * Unwraps the API error envelope ({ error: { message } }) or a plain
 * { message } response. Falls back to a generic string so stack traces
 * never surface to users.
 */
export function extractApiErrorMessage(error: unknown): string {
  if (error && typeof error === "object") {
    const shaped = error as ApiErrorShape;
    if (shaped.error?.message) return shaped.error.message;
    if (shaped.message) return shaped.message;
  }
  return extractErrorMessage(error);
}
