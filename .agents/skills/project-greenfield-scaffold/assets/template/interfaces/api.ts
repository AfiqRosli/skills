// Shared API response shapes — the success/error envelope every
// router returns so clients can branch on `code`, not message text.

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  timestamp?: string;
}

export interface ApiErrorBody {
  success: false;
  error: {
    message: string;
    code?: string;
    field?: string;
    timestamp: string;
  };
}
