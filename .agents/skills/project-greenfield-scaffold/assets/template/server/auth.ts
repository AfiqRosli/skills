import type { Elysia } from "elysia";
import { auth } from "@/auth";
// @flag billing
import { handlePolarWebhook } from "@/server/lib/polar-webhook";
// @endflag billing

/**
 * better-auth mount point. Everything under /api/auth/* is handled by
 * better-auth (sign-in, sign-up, session, verification, checkout).
 *
 * Webhook routes are registered BEFORE .mount(auth.handler) so Elysia
 * matches the specific POST route first — and with parse: "none" the raw
 * body bytes survive for signature validation (JSON parsing would
 * consume the stream).
 */
const authRouter = (app: Elysia) =>
  app
    // @flag billing
    .post("/auth/polar/webhooks", handlePolarWebhook, {
      parse: "none",
    })
    // @endflag billing
    .mount(auth.handler);

export default authRouter;
