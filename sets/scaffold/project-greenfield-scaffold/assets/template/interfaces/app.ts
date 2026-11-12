// Route vocabulary — single source of truth for which pages are guest,
// app, or protected. Layout selection (AppStore) and the auth guard
// (middleware/auth.global.ts) both read these lists; adding a page to a
// list here wires it into both.

export type LayoutType = "app" | "blank" | "minimal";

/** Pages for anonymous visitors — authed users get redirected away. */
export const GUEST_ROUTES = [
  "/sign-in",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
] as const;

/** Full app chrome (nav rail, user menu). */
export const APP_ROUTES = [
  "/",
] as const;

/** Require an authenticated session — anonymous users bounce to /sign-in. */
export const PROTECTED_ROUTES = [
  "/settings",
  "/profile",
] as const;
