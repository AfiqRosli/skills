import { Elysia, t } from "elysia";
import { sendEmail } from "./lib/email";
import { AuthenticationError } from "./errors";

/**
 * Email router — server-side transactional sends. Email should always
 * go through server/lib/email.ts (Resend, fail-safe logging); this
 * router exists for flows where a client action triggers an email.
 */
export default new Elysia({ prefix: "/email" })
  .post("/test", async ({ body }) => {
    if (process.env.NODE_ENV === "production") {
      throw new AuthenticationError("Test emails are dev-only");
    }
    await sendEmail(body.to, "Test email", "<p>It works.</p>");
    return { sent: true };
  }, {
    body: t.Object({
      to: t.String({ format: "email" }),
    }),
  });
