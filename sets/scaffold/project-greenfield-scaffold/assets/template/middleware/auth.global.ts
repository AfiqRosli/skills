import { useAuthStore } from "@/stores/AuthStore";
import { authClient } from "@/lib/auth-client";
import { GUEST_ROUTES, PROTECTED_ROUTES } from "@/interfaces/app";

const isProtectedRoute = (path: string): boolean =>
  PROTECTED_ROUTES.some(route => path.startsWith(route));

const isGuestRoute = (path: string): boolean =>
  GUEST_ROUTES.includes(path as typeof GUEST_ROUTES[number]);

/**
 * Global auth guard. Server-side session fetch happens only for routes
 * that need it — guest routes check the session so authed users get
 * redirected INTO the app; protected routes fetch so anonymous users
 * get bounced to /sign-in.
 *
 * Indexability interaction: never cache-redirect a guest page for an
 * authed user — routeRules must leave auth-flow pages uncached or the
 * redirect leaks across visitors.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore();

  if (!isProtectedRoute(to.path) && !isGuestRoute(to.path)) {
    return;
  }

  const { data: session } = await authClient.getSession({
    fetchOptions: {
      headers: import.meta.server ? useRequestHeaders(["cookie"]) : {},
    },
  });

  if (session?.user && !authStore.isAuthenticated) {
    authStore.setUser({
      id: session.user.id,
      name: session.user.name,
      email: session.user.email,
      image: session.user.image,
      createdAt: session.user.createdAt.toISOString(),
    });
  }

  if (isProtectedRoute(to.path) && !session?.user) {
    return navigateTo(`/sign-in?redirect=${encodeURIComponent(to.fullPath)}`);
  }

  if (isGuestRoute(to.path) && session?.user) {
    return navigateTo("/");
  }
});
