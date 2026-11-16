// Minimal Elysia `set` shape for header-writing middleware — importing
// Elysia's internal context types couples middleware to framework
// internals; this keeps server/api.ts helpers structurally typed.
import type { HTTPHeaders } from "elysia";

export interface SecurityHeaders {
  headers: HTTPHeaders;
  status?: number | string;
}
