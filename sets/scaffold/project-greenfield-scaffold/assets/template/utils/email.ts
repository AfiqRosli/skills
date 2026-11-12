/**
 * Normalize an email for storage/lookup — trim + lowercase so
 * " User@X.com " and "user@x.com" resolve to the same identity.
 */
export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}
