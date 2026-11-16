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

// @flag billing
// Fail fast on missing production secrets — prevents insecure defaults
// (empty webhook secret would allow forged state_changed events; missing
// product ID would create checkouts against a non-existent product).
const isProduction = process.env.NODE_ENV === "production";
const polarAccessToken = process.env.POLAR_ACCESS_TOKEN;
const polarWebhookSecret = process.env.POLAR_WEBHOOK_SECRET ?? "";
const polarProductIdMonthly = process.env.NUXT_POLAR_PRODUCT_ID_MONTHLY ?? "";

if (isProduction) {
  if (!polarAccessToken) {
    throw new Error(
      "POLAR_ACCESS_TOKEN is required in production — without it every "
      + "Polar SDK call fails authentication (checkouts, customer sync).",
    );
  }
  if (!polarWebhookSecret) {
    throw new Error(
      "POLAR_WEBHOOK_SECRET is required in production — without it, "
      + "webhook signature verification is disabled and forged events "
      + "could grant unauthorized access.",
    );
  }
  if (!polarProductIdMonthly) {
    throw new Error(
      "NUXT_POLAR_PRODUCT_ID_MONTHLY is required in production.",
    );
  }
}
else if (!polarWebhookSecret || !polarProductIdMonthly) {
  logger.warn("Polar configuration incomplete — using dev fallbacks", {
    missingWebhookSecret: !polarWebhookSecret,
    missingProductIdMonthly: !polarProductIdMonthly,
  });
}

export const polarClient = createPolarCore({
  accessToken: polarAccessToken!,
  environment:
    (process.env.POLAR_SERVER as "sandbox" | "production") || "sandbox",
});

// @endflag billing
export const auth = betterAuth({
  appName: "{{PROJECT_NAME}}",
  baseURL: process.env.BETTER_AUTH_URL!,
  trustedOrigins: [
    process.env.BETTER_AUTH_URL!,
    ...(process.env.NODE_ENV === "development"
      ? ["http://localhost:3000", "http://127.0.0.1:*"]
      : ["{{SITE_URL}}"]),
  ],
  plugins: [
    // @flag billing
    polar({
      client: polarClient,
      createCustomerOnSignUp: true,
      use: [
        checkout({
          products: [
            {
              productId: polarProductIdMonthly,
              slug: "monthly",
            },
          ],
          successUrl: "/thank-you?checkout_id={CHECKOUT_ID}",
          authenticatedUsersOnly: true,
        }),
        portal(),
      ],
    }),
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
