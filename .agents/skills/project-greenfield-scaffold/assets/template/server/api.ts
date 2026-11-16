import type { SecurityHeaders } from "@/interfaces/elysia";
import { Elysia } from "elysia";
import { cors } from "@elysiajs/cors";
import exampleRouter from "./example";
// @flag auth
import authRouter from "./auth";
// @endflag auth
// @flag email
import emailRouter from "./email";
// @endflag email
import { logger } from "@/utils/logger";

// Security headers configuration
const SECURITY_HEADERS = {
  csp: [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; "),
  xFrameOptions: "DENY",
  xContentTypeOptions: "nosniff",
  referrerPolicy: "strict-origin-when-cross-origin",
  permissionsPolicy: [
    "geolocation=()",
    "microphone=()",
    "camera=()",
    "payment=()",
    "usb=()",
    "magnetometer=()",
    "gyroscope=()",
    "accelerometer=()",
  ].join(", "),
} as const;

// CORS configuration — add preview/admin origins as the project grows.
// The dev server's bound origin must appear here or CSRF validation 403s
// browser POSTs — if nuxt dev binds a non-3000 port, add that origin.
const CORS_ORIGINS = [
  "{{SITE_URL}}",
  ...(process.env.NODE_ENV === "development" ? ["http://localhost:3000"] : []),
];

/**
 * Apply security headers to response
 */
function applySecurityHeaders(set: SecurityHeaders): void {
  set.headers["Content-Security-Policy"] = SECURITY_HEADERS.csp;
  set.headers["X-Frame-Options"] = SECURITY_HEADERS.xFrameOptions;
  set.headers["X-Content-Type-Options"] = SECURITY_HEADERS.xContentTypeOptions;
  set.headers["Referrer-Policy"] = SECURITY_HEADERS.referrerPolicy;
  set.headers["Permissions-Policy"] = SECURITY_HEADERS.permissionsPolicy;

  if (process.env.NODE_ENV === "production") {
    set.headers["Strict-Transport-Security"]
      = "max-age=31536000; includeSubDomains; preload";
  }
}

/**
 * State-changing HTTP methods that require CSRF protection.
 * GET/HEAD/OPTIONS are safe and excluded.
 */
const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Paths exempt from CSRF Origin validation.
 *
 * Server-to-server webhook endpoints receive POST requests from external
 * services that do NOT send an `Origin` header (it is a browser-only
 * concept). These endpoints authenticate via webhook signature
 * verification, not CSRF tokens. Without the exemption, webhook
 * deliveries are blocked with 403 in production.
 */
const CSRF_EXEMPT_PATHS = [
  // @flag billing
  "/api/auth/polar/webhooks",
  // @endflag billing
] as const;

/**
 * Check if a request path is exempt from CSRF validation.
 */
export function isCsrfExempt(request: Request): boolean {
  const pathname = new URL(request.url).pathname;
  return CSRF_EXEMPT_PATHS.some(path => pathname === path || pathname.startsWith(`${path}/`));
}

/**
 * CSRF protection via Origin header validation.
 * For state-changing requests, the Origin header must match an allowed
 * CORS origin. Browsers always send the real Origin on cross-origin
 * requests and it cannot be forged by JavaScript.
 */
export function validateOrigin(request: Request, set: SecurityHeaders): boolean {
  if (!STATE_CHANGING_METHODS.has(request.method.toUpperCase())) {
    return true;
  }

  if (isCsrfExempt(request)) {
    return true;
  }

  const origin = request.headers.get("origin");
  if (!origin) {
    // Same-origin requests from some browsers may omit Origin; allow in development.
    if (process.env.NODE_ENV === "development") return true;
    logger.warn("CSRF: missing Origin header on state-changing request", {
      method: request.method,
      url: request.url,
    });
    set.status = 403;
    return false;
  }

  if (!CORS_ORIGINS.includes(origin)) {
    logger.warn("CSRF: Origin not allowed", {
      method: request.method,
      origin,
      url: request.url,
    });
    set.status = 403;
    return false;
  }

  return true;
}

export default () =>
  new Elysia()
    // Security headers + CSRF protection middleware
    .onRequest(({ set, request }) => {
      applySecurityHeaders(set);
      if (!validateOrigin(request, set)) {
        return new Response(JSON.stringify({ error: "Origin not allowed" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        });
      }
    })
    // CORS configuration
    .use(
      cors({
        origin: CORS_ORIGINS,
        credentials: true,
        methods: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allowedHeaders: ["Content-Type", "Authorization", "X-Requested-With"],
      }),
    )
    .get("/hello", () => ({ message: "Hello Elysia!" }))
    .use(exampleRouter)
    // @flag auth
    .use(authRouter)
    // @endflag auth
    // @flag email
    .use(emailRouter)
    // @endflag email
    .get("/health", () => ({ status: "ok" }));
