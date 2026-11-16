import { createAuthClient } from "better-auth/vue";
// @flag billing
import type { BetterAuthClientPlugin } from "better-auth/client";
import { polarClient } from "@polar-sh/better-auth/client";

// polarClient()'s declared getActions signature was compiled against a
// different @better-fetch/fetch generic layout than the installed one —
// runtime-compatible but not assignable to BetterAuthClientPlugin. Its
// $InferServerPlugin endpoints are a conditional UnionToIntersection
// that evaluates keyof to `string`, which would erase the base auth API
// — so plugin endpoints (checkout, customer/portal) are called through
// $fetch in BillingStore instead of generated client methods.
const polar = polarClient() as unknown as BetterAuthClientPlugin;
// @endflag billing

export const authClient = createAuthClient({
  baseURL: process.env.BETTER_AUTH_URL,
  plugins: [
    // @flag billing
    polar,
    // @endflag billing
  ],
});
