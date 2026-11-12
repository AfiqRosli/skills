import { Resend } from "resend";
import { logger } from "@/utils/logger";

// Lazy client — `new Resend()` throws without a key, so constructing at
// module load would 500 every request on machines without RESEND_API_KEY.
// getResend() returns null when unconfigured; senders log and no-op.
let resend: Resend | null = null;

function getResend(): Resend | null {
  if (resend) return resend;
  const key = process.env.RESEND_API_KEY;
  if (!key) return null;
  resend = new Resend(key);
  return resend;
}

const from = process.env.EMAIL_FROM || "{{PROJECT_NAME}} <noreply@example.com>";

/**
 * Transactional email via Resend. Called from auth.ts callbacks
 * (verification, password reset) and anywhere else a lifecycle email is
 * needed. Failures are logged, not thrown — a lost email must not fail
 * the signup/reset request that triggered it. Queuing durable retries
 * is a future-layer concern.
 */
export async function sendEmail(
  to: string,
  subject: string,
  html: string,
): Promise<void> {
  const client = getResend();
  if (!client) {
    logger.warn("RESEND_API_KEY not configured — skipping email", { to, subject });
    return;
  }
  try {
    await client.emails.send({ from, to, subject, html });
  }
  catch (error) {
    logger.error("Email send failed", { to, subject, error });
  }
}

export async function sendVerificationEmail(
  to: string,
  url: string,
): Promise<void> {
  await sendEmail(
    to,
    `Verify your {{PROJECT_NAME}} email`,
    `<p>Confirm your email address:</p><p><a href="${url}">${url}</a></p>`,
  );
}

export async function sendPasswordResetEmail(
  to: string,
  url: string,
): Promise<void> {
  await sendEmail(
    to,
    `Reset your {{PROJECT_NAME}} password`,
    `<p>Reset your password:</p><p><a href="${url}">${url}</a></p>`,
  );
}
