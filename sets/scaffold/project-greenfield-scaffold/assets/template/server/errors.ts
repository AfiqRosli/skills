/**
 * Custom error classes for API error handling.
 * Consistent error responses: every ApiError carries an HTTP status and
 * a machine-readable code so clients can branch on `code`, not message.
 */

export class ApiError extends Error {
  constructor(
    message: string,
    public _statusCode: number = 500,
    public _code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ValidationError extends ApiError {
  constructor(
    message: string,
    public _field?: string,
  ) {
    super(message, 400, "VALIDATION_ERROR");
    this.name = "ValidationError";
  }
}

export class NotFoundError extends ApiError {
  constructor(message: string = "Resource not found") {
    super(message, 404, "NOT_FOUND");
    this.name = "NotFoundError";
  }
}

export class AuthenticationError extends ApiError {
  constructor(
    message: string = "Authentication failed",
    public code: "INVALID_CREDENTIALS" | "TOKEN_EXPIRED" | "INSUFFICIENT_PERMISSIONS" = "INVALID_CREDENTIALS",
  ) {
    super(message, 401, code);
    this.name = "AuthenticationError";
  }
}

export class AuthorizationError extends ApiError {
  constructor(message: string = "Insufficient permissions") {
    super(message, 403, "INSUFFICIENT_PERMISSIONS");
    this.name = "AuthorizationError";
  }
}

export class ExternalServiceError extends ApiError {
  constructor(
    message: string,
    public _service: string,
    public _originalError?: Error,
  ) {
    super(message, 502, "EXTERNAL_SERVICE_ERROR");
    this.name = "ExternalServiceError";
  }
}
