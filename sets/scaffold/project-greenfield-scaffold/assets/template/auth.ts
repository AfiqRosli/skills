import { randomBytes } from "node:crypto";
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
// @flag billing
import { polar, checkout, portal } from "@polar-sh/better-auth";
// Versioned SDK import — the path pins every request to a dated API
// contract via the Polar-Version header. The legacy `Polar` class no
// longer exists at the package root in SDK v1.
import { createPolarCore } from "@polar-sh/sdk/2026-10";
// @endflag billing
import db from "./server/db/index";
import * as schema from "./server/db/schema";
import { logger } from "./utils/logger";

// Missing env degrades the routes that need it, never the process —
// this file is in the transitive import graph of every API route, so a
// throw at module eval 500s everything. Degraded mode is loud in logs
// (one boot warning naming every gap) and refuses the dangerous route
// rather than failing silently: an empty webhook secret or bogus
// product ID is a security hole, not just an outage.
// @flag billing
const polarAccessToken = process.env.POLAR_ACCESS_TOKEN;
const polarWebhookSecret = process.env.POLAR_WEBHOOK_SECRET;
const polarProductIdMonthly = process.env.NUXT_POLAR_PRODUCT_ID_MONTHLY;

// polarClient builds only when checkout can actually succeed — no SDK
// instance holding an empty access token.
export const polarClient =
  polarAccessToken && polarProductIdMonthly
    ? createPolarCore({
        accessToken: polarAccessToken,
        environment:
          (process.env.POLAR_SERVER as "sandbox" | "production") || "sandbox",
      })
    : null;
// @endflag billing

const missingAuthEnv = [
  !process.env.BETTER_AUTH_SECRET &&
    "BETTER_AUTH_SECRET (ephemeral per-boot secret in use — sessions die on restart)",
  // @flag billing
  !polarAccessToken && "POLAR_ACCESS_TOKEN",
  !polarWebhookSecret && "POLAR_WEBHOOK_SECRET",
  !polarProductIdMonthly && "NUXT_POLAR_PRODUCT_ID_MONTHLY",
  // @endflag billing
].filter(Boolean);
if (missingAuthEnv.length) {
  logger.warn("auth env incomplete — running degraded", {
    missing: missingAuthEnv,
  });
}

// Falls back through host-provided env (Netlify sets DEPLOY_PRIME_URL)
// so auth stays mounted without explicit config.
const baseURL =
  process.env.BETTER_AUTH_URL ??
  process.env.NUXT_PUBLIC_APP_URL ??
  process.env.DEPLOY_PRIME_URL ??
  "http://localhost:3000";

export const auth = betterAuth({
  appName: "{{PROJECT_NAME}}",
  baseURL,
  // better-auth throws inside its request handler when secret is unset
  // — and .mount(auth.handler) fans that out to every route. An
  // ephemeral per-boot secret keeps auth mounted; the boot warning
  // above names the gap (sessions do not survive a restart).
  secret: process.env.BETTER_AUTH_SECRET ?? randomBytes(32).toString("hex"),
  trustedOrigins: [
    baseURL,
    ...(process.env.NODE_ENV === "development"
      ? ["http://localhost:3000", "http://127.0.0.1:*"]
      : ["{{SITE_URL}}"]),
  ],
  plugins: [
    // @flag billing
    ...(polarClient
      ? [
          polar({
            client: polarClient,
            createCustomerOnSignUp: true,
            use: [
              checkout({
                products: [
                  {
                    productId: polarProductIdMonthly!,
                    slug: "monthly",
                  },
                ],
                successUrl: "/thank-you?checkout_id={CHECKOUT_ID}",
                authenticatedUsersOnly: true,
              }),
              portal(),
            ],
          }),
        ]
      : []),
    // @endflag billing
  ],
  database: drizzleAdapter(db, {
    provider: "pg",
    schema,
  }),
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    // @flag email
    sendResetPassword: async ({ user, url }) => {
      const { sendPasswordResetEmail } = await import(
        "./server/lib/email"
      );
      await sendPasswordResetEmail(user.email, url);
    },
    // @endflag email
  },
  emailVerification: {
    sendOnSignUp: true,
    autoSignInAfterVerification: true,
    // @flag email
    sendVerificationEmail: async ({ user, url }) => {
      const { sendVerificationEmail } = await import("./server/lib/email");
      await sendVerificationEmail(user.email, url);
    },
    // @endflag email
  },
  // Providers wire only when their credentials exist — an unconfigured
  // provider warns at every boot and yields a dead /sign-in/social route.
  socialProviders: {
    ...(process.env.GOOGLE_CLIENT_ID
      ? {
        google: {
          clientId: process.env.GOOGLE_CLIENT_ID,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
        },
      }
      : {}),
  },
});
