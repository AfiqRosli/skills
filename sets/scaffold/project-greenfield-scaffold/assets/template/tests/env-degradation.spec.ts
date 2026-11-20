import { describe, expect, it, vi } from "vitest";

/**
 * Env-missing must never be a module-load failure. Simulates the
 * Netlify cold-start failure mode: every app env var unset under
 * NODE_ENV=production. The server module graph must still import, a
 * non-DB route must still respond 200, and DB access must throw its
 * own error — not crash the process at import.
 */
const APP_ENV_VARS = [
  "DATABASE_URL",
  "BETTER_AUTH_URL",
  "BETTER_AUTH_SECRET",
  // @flag billing
  "POLAR_ACCESS_TOKEN",
  "POLAR_WEBHOOK_SECRET",
  "NUXT_POLAR_PRODUCT_ID_MONTHLY",
  // @endflag billing
  "NUXT_PUBLIC_APP_URL",
  "DEPLOY_PRIME_URL",
  "GOOGLE_CLIENT_ID",
  "GOOGLE_CLIENT_SECRET",
  "RESEND_API_KEY",
  "EMAIL_FROM",
  "REDIS_URL",
  "SENTRY_DSN",
];

describe("env-missing cold start", () => {
  it("imports the server graph and serves non-DB routes with all app env unset", async () => {
    const saved: Record<string, string | undefined> = {};
    for (const key of APP_ENV_VARS) {
      saved[key] = process.env[key];
      delete process.env[key];
    }
    const nodeEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = "production";
    try {
      // resetModules re-runs import-time code against the stripped
      // env — the same path a serverless cold start takes.
      vi.resetModules();
      const { default: createApi } = await import("../server/api");
      const res = await createApi().handle(
        new Request("http://localhost/hello"),
      );
      expect(res.status).toBe(200);

      // @flag db
      // The template ships no DB route — the proxy assertion covers
      // the DB path: the import above did not throw; first access does.
      const { default: db } = await import("../server/db/index");
      expect(() => db.select).toThrow(/DATABASE_URL/);
      // @endflag db
    }
    finally {
      for (const key of APP_ENV_VARS) {
        if (saved[key] === undefined) delete process.env[key];
        else process.env[key] = saved[key] as string;
      }
      if (nodeEnv === undefined) delete process.env.NODE_ENV;
      else process.env.NODE_ENV = nodeEnv;
    }
  });
});
