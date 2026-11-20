import { logger } from "@/utils/logger";

/**
 * Polar webhook handler — registered before .mount(auth.handler) with
 * parse: "none", so `request.text()` still yields the raw body bytes the
 * signature check needs.
 *
 * Signature verification happens inside @polar-sh/better-auth's
 * webhooks() handler once wired; this stub preserves the routing
 * contract and shows where subscription lifecycle events land. While
 * POLAR_WEBHOOK_SECRET is unset the route refuses 503 — accepting
 * unsigned state_changed events is a security hole, not an outage.
 * auth.ts lists the gap in its boot warning.
 */
export async function handlePolarWebhook({ request }: { request: Request }) {
  if (!process.env.POLAR_WEBHOOK_SECRET) {
    logger.warn("Polar webhook rejected — POLAR_WEBHOOK_SECRET unset");
    return new Response(JSON.stringify({ error: "Webhook not configured" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }

  const rawBody = await request.text();
  const signature = request.headers.get("webhook-signature");

  if (!signature) {
    return new Response(JSON.stringify({ error: "Missing signature" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    // Verify signature + dispatch customer.state_changed /
    // subscription.* events here.
    const event = JSON.parse(rawBody);
    logger.info("Polar webhook received", { type: event?.type });
    return { received: true };
  }
  catch {
    return new Response(JSON.stringify({ error: "Invalid payload" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
}
